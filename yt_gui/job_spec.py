"""ダウンロードジョブの実行設定を表す DTO と、`format_id` 派生ラダーの集約。

リファクタリング前は同じラダー (format_id → format_spec / embed_thumbnail /
audio_codec / mp3_bitrate / video_container / embed_metadata / embed_chapters)
が app.py の 3 箇所 (_add_url / _apply_edit / _enqueue_playlist) に
重複していた。本モジュールはそれを `build_job_spec()` 1 箇所に集約する
pure function とする (UI 依存ゼロ、テスト容易)。

関連仕様:
- docs/spec/features/download-formats.md
- docs/spec/features/download-behavior.md
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .formats import build_720p_spec, build_best_spec
from .settings import Settings

_ORIGINAL_KEY = "fmt_original"
_MP3_KEY = "fmt_mp3"
_BEST_MP4_KEY = "fmt_best_mp4"
_720P_KEY = "fmt_720p"


@dataclass(frozen=True)
class PanelSnapshot:
    """OriginalFormatPanel の選択状態のスナップショット (fmt_original 用)。

    `format_spec` と各 bool は panel の getter から既に解決された値を持つ。
    `raw_settings` は復元 (restore_from_settings) と nico_comments 取り出し
    のために panel.get_raw_settings() の dict をそのまま保持する。
    """

    format_spec: str
    subtitle_opts: dict | None
    remux_only: bool
    audio_only: bool
    embed_thumbnail: bool
    embed_metadata: bool
    embed_chapters: bool
    has_multiple_audio: bool
    raw_settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobSpec:
    """1 ジョブの実行設定。`Downloader.download_video()` の入力となる。"""

    format_id: str
    format_spec: str
    subtitle_opts: dict | None
    embed_thumbnail: bool
    embed_metadata: bool
    embed_chapters: bool
    audio_codec: str
    mp3_bitrate: str | None
    video_container: str
    audio_only: bool
    remux_only: bool
    orig_settings: dict | None
    is_multi_audio: bool
    # 区間ダウンロード (yt-dlp --download-sections 相当)。生の入力文字列を保持し、
    # 秒への変換は downloader 側で行う。形式非依存・アイテム単位。
    section_start: str | None = None
    section_end: str | None = None
    section_force_keyframes: bool = False

    @property
    def is_audio_extraction(self) -> bool:
        """ffmpeg で音声抽出経路に入るか (fmt_mp3 or fmt_original + audio_only)。"""
        return self.audio_only or self.format_id == _MP3_KEY


def build_job_spec(
    format_id: str,
    settings: Settings,
    *,
    panel: PanelSnapshot | None = None,
    mp3_thumb_check: bool = False,
    section_start: str | None = None,
    section_end: str | None = None,
    section_force_keyframes: bool = False,
) -> JobSpec:
    """`format_id` から `JobSpec` を組み立てる pure function。

    - `fmt_original` のときは `panel` 必須。
    - `fmt_mp3` のときは `mp3_thumb_check` がサムネ埋め込みチェック状態。
    - `section_*` は区間ダウンロードの設定。形式非依存で、指定されていれば
      末尾で全 format_id の JobSpec へ一律付与する。
    - その他の format_id でも防御的に値を返す (catch-all)。
    """
    spec = _dispatch_job_spec(format_id, settings, panel, mp3_thumb_check)
    if section_start or section_end or section_force_keyframes:
        spec = replace(
            spec,
            section_start=section_start,
            section_end=section_end,
            section_force_keyframes=section_force_keyframes,
        )
    return spec


def _dispatch_job_spec(
    format_id: str,
    settings: Settings,
    panel: PanelSnapshot | None,
    mp3_thumb_check: bool,
) -> JobSpec:
    if format_id == _ORIGINAL_KEY:
        if panel is None:
            raise ValueError("panel is required for fmt_original")
        return _build_original_spec(settings, panel)
    if format_id == _MP3_KEY:
        return _build_mp3_spec(settings, mp3_thumb_check)
    if format_id == _720P_KEY:
        return _build_720p_jobspec(settings)
    if format_id == _BEST_MP4_KEY:
        return _build_best_mp4_jobspec(settings)
    # 未知の format_id: 最低限の値で防御的に返す
    return JobSpec(
        format_id=format_id,
        format_spec="best/best",
        subtitle_opts=None,
        embed_thumbnail=False,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec="mp3",
        mp3_bitrate=None,
        video_container=settings.video_container,
        audio_only=False,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    )


# ── 内部: format_id 別の組み立て ──────────────────────────────────────────


def _build_best_mp4_jobspec(settings: Settings) -> JobSpec:
    container = settings.video_container
    return JobSpec(
        format_id=_BEST_MP4_KEY,
        format_spec=build_best_spec(container),
        subtitle_opts=None,
        embed_thumbnail=True,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec="mp3",
        mp3_bitrate=None,
        video_container=container,
        audio_only=False,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    )


def _build_720p_jobspec(settings: Settings) -> JobSpec:
    container = settings.video_container
    return JobSpec(
        format_id=_720P_KEY,
        format_spec=build_720p_spec(settings.video_resolution, container),
        subtitle_opts=None,
        embed_thumbnail=True,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec="mp3",
        mp3_bitrate=None,
        video_container=container,
        audio_only=False,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    )


def _build_mp3_spec(settings: Settings, mp3_thumb_check: bool) -> JobSpec:
    audio_codec = settings.audio_format
    is_mp3 = audio_codec == "mp3"
    return JobSpec(
        format_id=_MP3_KEY,
        format_spec="bestaudio/best",
        subtitle_opts=None,
        embed_thumbnail=mp3_thumb_check if is_mp3 else False,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec=audio_codec,
        mp3_bitrate=settings.mp3_bitrate if is_mp3 else None,
        video_container=settings.video_container,
        audio_only=True,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    )


def _build_original_spec(settings: Settings, panel: PanelSnapshot) -> JobSpec:
    audio_only = panel.audio_only
    remux_only = panel.remux_only

    # 通常結合モードで複数音声選択 → コンテナを mkv に昇格
    is_multi_audio = panel.has_multiple_audio and not audio_only and not remux_only
    video_container = (
        "mkv"
        if is_multi_audio and settings.video_container != "mkv"
        else settings.video_container
    )

    audio_codec = settings.audio_format if audio_only else "mp3"
    is_mp3 = audio_codec == "mp3"
    mp3_bitrate = settings.mp3_bitrate if audio_only and is_mp3 else None

    return JobSpec(
        format_id=_ORIGINAL_KEY,
        format_spec=panel.format_spec,
        subtitle_opts=panel.subtitle_opts,
        embed_thumbnail=panel.embed_thumbnail,
        embed_metadata=panel.embed_metadata,
        embed_chapters=panel.embed_chapters,
        audio_codec=audio_codec,
        mp3_bitrate=mp3_bitrate,
        video_container=video_container,
        audio_only=audio_only,
        remux_only=remux_only,
        orig_settings=panel.raw_settings,
        is_multi_audio=is_multi_audio,
    )
