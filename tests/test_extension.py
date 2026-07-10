"""ブラウザ拡張（`extension/`）の整合性テスト。

- `scripts/sync_extension_version.py` のバージョン同期ロジック
- `extension/manifest.json` の MV3 妥当性（default_locale / icons / 英語化）
- `_locales/` の en / ja キー整合
- アイコン PNG の実サイズ

仕様: docs/spec/features/browser-extension.md
"""

import importlib.util
import json
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EXT = os.path.join(_ROOT, "extension")
_SCRIPTS = os.path.join(_ROOT, "scripts")


def _load(name):
    path = os.path.join(_SCRIPTS, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync_mod = _load("sync_extension_version")


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _pyproject_version():
    import tomllib

    with open(os.path.join(_ROOT, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


# --- バージョン同期 --------------------------------------------------------


def test_read_project_version_matches_pyproject():
    assert (
        sync_mod.read_project_version(os.path.join(_ROOT, "pyproject.toml"))
        == _pyproject_version()
    )


def test_sync_manifest_version_writes_and_is_idempotent(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"manifest_version": 3, "version": "0.0.0"}), encoding="utf-8"
    )
    changed = sync_mod.sync_manifest_version(str(manifest), "1.2.3")
    assert changed is True
    assert _read_json(manifest)["version"] == "1.2.3"
    # 2 回目は変更なし
    assert sync_mod.sync_manifest_version(str(manifest), "1.2.3") is False


def test_committed_manifest_version_in_sync_with_pyproject():
    manifest = _read_json(os.path.join(_EXT, "manifest.json"))
    assert manifest["version"] == _pyproject_version()


# --- manifest 妥当性 -------------------------------------------------------


def test_manifest_is_valid_mv3():
    m = _read_json(os.path.join(_EXT, "manifest.json"))
    assert m["manifest_version"] == 3
    assert m["default_locale"] == "en"
    # name / description は英語固定（ASCII のみ）
    assert m["name"].isascii()
    assert m["description"].isascii()


def test_manifest_declares_popup():
    """action に default_popup を宣言し、popup ファイルが存在する。"""
    m = _read_json(os.path.join(_EXT, "manifest.json"))
    popup = m["action"]["default_popup"]
    assert os.path.isfile(os.path.join(_EXT, popup)), popup
    assert os.path.isfile(os.path.join(_EXT, "popup.js"))


def test_manifest_declares_context_menus_permission():
    """右クリックメニュー（即送信）用に contextMenus 権限を宣言する。"""
    m = _read_json(os.path.join(_EXT, "manifest.json"))
    assert "contextMenus" in m["permissions"]


def test_manifest_declares_icons_for_all_sizes():
    m = _read_json(os.path.join(_EXT, "manifest.json"))
    for sizes_block in (m["icons"], m["action"]["default_icon"]):
        for size in ("16", "32", "48", "128"):
            rel = sizes_block[size]
            assert os.path.isfile(os.path.join(_EXT, rel)), rel


# --- _locales --------------------------------------------------------------


def test_locales_en_ja_have_identical_keys():
    en = _read_json(os.path.join(_EXT, "_locales", "en", "messages.json"))
    ja = _read_json(os.path.join(_EXT, "_locales", "ja", "messages.json"))
    assert set(en) == set(ja)
    assert en  # 空でない
    for block in (*en.values(), *ja.values()):
        assert "message" in block


# --- オリジナル形式の選択肢（Issue #151） ---------------------------------


def test_popup_offers_original_kind_option():
    """popup.html の形式セレクタに original（アプリで選択）の選択肢がある。"""
    with open(os.path.join(_EXT, "popup.html"), encoding="utf-8") as fh:
        html = fh.read()
    assert 'value="original"' in html


def test_locales_define_original_kind_label():
    """en / ja 双方に kindOriginal ラベルが定義されている。"""
    for lang in ("en", "ja"):
        msgs = _read_json(os.path.join(_EXT, "_locales", lang, "messages.json"))
        assert "kindOriginal" in msgs
        assert msgs["kindOriginal"]["message"].strip()


# --- アイコン実サイズ ------------------------------------------------------


def test_icon_files_have_expected_pixel_sizes():
    pil_image = pytest.importorskip("PIL.Image")
    m = _read_json(os.path.join(_EXT, "manifest.json"))
    for size, rel in m["icons"].items():
        with pil_image.open(os.path.join(_EXT, rel)) as im:
            assert im.size == (int(size), int(size)), rel
