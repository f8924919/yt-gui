"""yt_gui.i18n のテスト。

対応仕様: docs/spec/i18n.md
"""

import pytest

from yt_gui import i18n
from yt_gui.i18n import AVAILABLE_LANGUAGES, set_language, t


def test_available_languages_matches_spec() -> None:
    assert AVAILABLE_LANGUAGES == ["ja", "en"]


@pytest.mark.parametrize(
    "lang, key, expected",
    [
        ("ja", "btn_add", "追加"),
        ("en", "btn_add", "Add"),
    ],
)
def test_t_returns_translation_for_current_language(
    lang: str, key: str, expected: str
) -> None:
    set_language(lang)
    assert t(key) == expected


def test_set_language_ignores_unknown_code() -> None:
    set_language("ja")
    set_language("zz")  # 未定義言語は無視される
    assert i18n._current_lang == "ja"


def test_t_falls_back_to_japanese_when_key_missing_in_current_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(i18n._LANGUAGES, "en", {})  # en から全キー削除
    set_language("en")
    assert t("btn_add") == "追加"


def test_t_returns_key_when_missing_everywhere() -> None:
    set_language("ja")
    assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_all_locales_share_identical_keys() -> None:
    """全言語ファイルは同一キー集合を持つ（翻訳漏れがフォールバックで隠れるのを防ぐ）。

    対応仕様: docs/spec/i18n.md § キーの整合性（全言語で同一キー）
    """
    key_sets = {lang: set(strings) for lang, strings in i18n._LANGUAGES.items()}
    base_lang, base_keys = next(iter(key_sets.items()))
    for lang, keys in key_sets.items():
        assert keys == base_keys, (
            f"{lang} のキーが {base_lang} と不一致: "
            f"{base_lang}のみ={sorted(base_keys - keys)} / "
            f"{lang}のみ={sorted(keys - base_keys)}"
        )
