"""OUTPUT TEMPLATE 関連の定数と検証/プレビュー用ヘルパ。

yt-dlp の OUTPUT TEMPLATE はかなり広い機能を持つが、ここでは UI で「挿入」できる
代表的なフィールドのみを `TEMPLATE_FIELDS` に列挙する。すべての構文は
yt-dlp 公式ドキュメントを参照する想定。
"""

from typing import Any

DEFAULT_VIDEO_TEMPLATE: str = "%(title)s.%(ext)s"
DEFAULT_PLAYLIST_TEMPLATE: str = (
    "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
)

YTDLP_OUTPUT_TEMPLATE_DOC_URL: str = "https://github.com/yt-dlp/yt-dlp#output-template"

# (挿入文字列, i18n キーのサフィックス)
TEMPLATE_FIELDS: list[tuple[str, str]] = [
    ("%(title)s", "title"),
    ("%(uploader)s", "uploader"),
    ("%(upload_date)s", "upload_date"),
    ("%(playlist_title)s", "playlist_title"),
    ("%(playlist_index)s", "playlist_index"),
    ("%(playlist_index)03d", "playlist_index_padded"),
    ("%(ext)s", "ext"),
]

# プレビュー生成用のサンプル
SAMPLE_INFO: dict[str, Any] = {
    "title": "Sample Video",
    "uploader": "Sample Channel",
    "upload_date": "20260101",
    "playlist_title": "My Playlist",
    "playlist_index": 1,
    "ext": "mp4",
}


def render_preview(template: str) -> str | None:
    """テンプレートを `SAMPLE_INFO` で展開して文字列を返す。展開に失敗したら None。"""
    try:
        return template % SAMPLE_INFO
    except Exception:
        return None


def validate_template(template: str) -> str | None:
    """テンプレートを検証し、エラーがあれば i18n キーを返す。問題なければ None。"""
    if not template.strip():
        return "warn_template_invalid"
    if "%(ext)s" not in template:
        return "warn_template_no_ext"
    if render_preview(template) is None:
        return "warn_template_invalid"
    return None
