#!/usr/bin/env python3
"""ブラウザ拡張の `manifest.json` の version をアプリ本体に同期する。

単一ソースは `pyproject.toml` の `[project] version`。リリース時に CI が拡張 zip を
固める直前に実行し、配布物の version をアプリ本体と一致させる（実行時の動的同期は
しない）。手元でアプリのバージョンを上げたあとにも実行してコミット版を揃える。

仕様: docs/spec/features/browser-extension.md（バージョン同期）

使い方:
    python scripts/sync_extension_version.py          # 書き換えて結果を表示
    python scripts/sync_extension_version.py --check  # 差分があれば非ゼロ終了
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYPROJECT = os.path.join(_ROOT, "pyproject.toml")
_MANIFEST = os.path.join(_ROOT, "extension", "manifest.json")


def read_project_version(pyproject_path: str = _PYPROJECT) -> str:
    """`pyproject.toml` の `[project] version` を返す。"""
    with open(pyproject_path, "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def sync_manifest_version(manifest_path: str, version: str) -> bool:
    """`manifest.json` の version を `version` に書き換える。

    変更があった場合のみ書き込み、`True` を返す（冪等）。JSON の整形は 2 スペース
    インデント・末尾改行で固定し、非 ASCII はそのまま保持する。
    """
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    if manifest.get("version") == version:
        return False

    manifest["version"] = version
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き換えず、差分があれば非ゼロ終了する",
    )
    args = parser.parse_args(argv)

    version = read_project_version()
    with open(_MANIFEST, encoding="utf-8") as fh:
        current = json.load(fh).get("version")

    if args.check:
        if current != version:
            print(
                f"manifest version {current!r} != pyproject {version!r}",
                file=sys.stderr,
            )
            return 1
        print(f"in sync: {version}")
        return 0

    changed = sync_manifest_version(_MANIFEST, version)
    if changed:
        print(f"updated extension version: {current} -> {version}")
    else:
        print(f"already in sync: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
