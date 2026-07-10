#!/usr/bin/env python3
"""アプリ本体のアイコン（`assets/icon.png`）からブラウザ拡張用アイコンを生成する。

`extension/icons/icon-{size}.png`（16/32/48/128 px）を Lanczos 縮小で書き出す。
生成物はコミットする（unpacked 読み込み・zip 配布のいずれでも同梱が必要なため）。

仕様: docs/spec/features/browser-extension.md（アイコン）

使い方:
    python scripts/build_extension_icons.py
"""

from __future__ import annotations

import os

from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "assets", "icon.png")
_OUT_DIR = os.path.join(_ROOT, "extension", "icons")
SIZES = (16, 32, 48, 128)


def build_icons(src: str = _SRC, out_dir: str = _OUT_DIR) -> list[str]:
    """各サイズの PNG を生成し、書き出したパスの一覧を返す。"""
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        for size in SIZES:
            resized = rgba.resize((size, size), Image.Resampling.LANCZOS)
            path = os.path.join(out_dir, f"icon-{size}.png")
            resized.save(path, format="PNG")
            written.append(path)
    return written


def main() -> int:
    for path in build_icons():
        print(f"wrote {os.path.relpath(path, _ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
