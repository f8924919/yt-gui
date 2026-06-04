"""yt_gui.job_spec のテスト。

対応仕様:
- docs/spec/features/download-formats.md
- docs/spec/features/download-behavior.md

`build_job_spec(format_id, settings, *, panel, mp3_thumb_check)` が
追加 (_add_url) / 編集 (_apply_edit) / プレイリスト (_enqueue_playlist) の
3 箇所で重複していた `format_id → 設定一式` のラダーを単一実装に集約することを
確認するためのテーブルテスト。
"""

from __future__ import annotations

import pytest

from yt_gui.formats import build_720p_spec, build_best_spec
from yt_gui.job_spec import JobSpec, PanelSnapshot, build_job_spec
from yt_gui.settings import Settings

# ── helpers ───────────────────────────────────────────────────────────────


def _panel(
    *,
    format_spec: str = "137+140",
    subtitle_opts: dict | None = None,
    remux_only: bool = False,
    audio_only: bool = False,
    embed_thumbnail: bool = True,
    embed_metadata: bool = True,
    embed_chapters: bool = True,
    has_multiple_audio: bool = False,
    raw_settings: dict | None = None,
) -> PanelSnapshot:
    return PanelSnapshot(
        format_spec=format_spec,
        subtitle_opts=subtitle_opts,
        remux_only=remux_only,
        audio_only=audio_only,
        embed_thumbnail=embed_thumbnail,
        embed_metadata=embed_metadata,
        embed_chapters=embed_chapters,
        has_multiple_audio=has_multiple_audio,
        raw_settings=raw_settings if raw_settings is not None else {},
    )


# ── fmt_best_mp4 ──────────────────────────────────────────────────────────


def test_best_mp4_basic() -> None:
    job = build_job_spec("fmt_best_mp4", Settings())
    assert job.format_id == "fmt_best_mp4"
    assert job.format_spec == build_best_spec("mp4")
    assert job.audio_only is False
    assert job.audio_codec == "mp3"
    assert job.mp3_bitrate is None
    assert job.embed_thumbnail is True
    assert job.embed_metadata is True
    assert job.embed_chapters is True
    assert job.video_container == "mp4"
    assert job.remux_only is False
    assert job.subtitle_opts is None
    assert job.orig_settings is None
    assert job.is_multi_audio is False
    assert job.is_audio_extraction is False


def test_best_mp4_uses_settings_container() -> None:
    job = build_job_spec("fmt_best_mp4", Settings(video_container="mkv"))
    assert job.format_spec == build_best_spec("mkv")
    assert job.video_container == "mkv"


# ── fmt_720p ──────────────────────────────────────────────────────────────


def test_720p_uses_settings_resolution_and_container() -> None:
    settings = Settings(video_resolution="1080", video_container="webm")
    job = build_job_spec("fmt_720p", settings)
    assert job.format_id == "fmt_720p"
    assert job.format_spec == build_720p_spec("1080", "webm")
    assert job.video_container == "webm"
    assert job.embed_thumbnail is True
    assert job.audio_only is False
    assert job.is_audio_extraction is False


# ── fmt_mp3 ───────────────────────────────────────────────────────────────


def test_mp3_with_thumb_check_on() -> None:
    settings = Settings(audio_format="mp3", mp3_bitrate="192")
    job = build_job_spec("fmt_mp3", settings, mp3_thumb_check=True)
    assert job.format_id == "fmt_mp3"
    assert job.audio_only is True
    assert job.audio_codec == "mp3"
    assert job.mp3_bitrate == "192"
    assert job.embed_thumbnail is True
    assert job.is_audio_extraction is True
    # サブタイトル系は無し
    assert job.subtitle_opts is None
    # フォーマット spec は yt-dlp 標準の bestaudio
    assert job.format_spec == "bestaudio/best"


def test_mp3_with_thumb_check_off() -> None:
    settings = Settings(audio_format="mp3", mp3_bitrate="320")
    job = build_job_spec("fmt_mp3", settings, mp3_thumb_check=False)
    assert job.embed_thumbnail is False
    assert job.mp3_bitrate == "320"


def test_flac_thumb_check_ignored() -> None:
    """audio_format=flac のときは mp3_thumb_check 値に関わらず False、bitrate も None。

    mp3 専用のチェック状態は flac へ波及しない。
    """
    settings = Settings(audio_format="flac", mp3_bitrate="192")
    job = build_job_spec("fmt_mp3", settings, mp3_thumb_check=True)
    assert job.audio_codec == "flac"
    assert job.embed_thumbnail is False
    assert job.mp3_bitrate is None


# ── fmt_original ──────────────────────────────────────────────────────────


def test_original_video_audio_combined() -> None:
    panel = _panel(format_spec="137+140")
    job = build_job_spec("fmt_original", Settings(), panel=panel)
    assert job.format_id == "fmt_original"
    assert job.format_spec == "137+140"
    assert job.audio_only is False
    assert job.audio_codec == "mp3"
    assert job.mp3_bitrate is None
    assert job.video_container == "mp4"
    assert job.is_multi_audio is False
    assert job.is_audio_extraction is False
    assert job.embed_thumbnail is True
    assert job.embed_metadata is True
    assert job.embed_chapters is True


def test_original_multi_audio_promotes_to_mkv() -> None:
    """has_multiple_audio=True かつ通常結合モード → コンテナを mkv に昇格。"""
    panel = _panel(format_spec="137+140+141", has_multiple_audio=True)
    job = build_job_spec("fmt_original", Settings(video_container="mp4"), panel=panel)
    assert job.video_container == "mkv"
    assert job.is_multi_audio is True


def test_original_multi_audio_no_promotion_when_remux_only() -> None:
    """remux_only=True のときは昇格しない。"""
    panel = _panel(
        format_spec="137",
        has_multiple_audio=True,
        remux_only=True,
    )
    job = build_job_spec("fmt_original", Settings(video_container="mp4"), panel=panel)
    assert job.video_container == "mp4"
    assert job.is_multi_audio is False
    assert job.remux_only is True


def test_original_audio_only_mp3() -> None:
    panel = _panel(
        format_spec="140",
        audio_only=True,
        embed_thumbnail=True,
    )
    job = build_job_spec(
        "fmt_original",
        Settings(audio_format="mp3", mp3_bitrate="256"),
        panel=panel,
    )
    assert job.audio_only is True
    assert job.audio_codec == "mp3"
    assert job.mp3_bitrate == "256"
    assert job.embed_thumbnail is True
    assert job.is_audio_extraction is True


def test_original_audio_only_flac_no_bitrate() -> None:
    """audio_only=True で flac のときは mp3_bitrate=None。"""
    panel = _panel(format_spec="140", audio_only=True)
    job = build_job_spec(
        "fmt_original",
        Settings(audio_format="flac", mp3_bitrate="192"),
        panel=panel,
    )
    assert job.audio_codec == "flac"
    assert job.mp3_bitrate is None


def test_original_subtitle_opts_passthrough() -> None:
    """subtitle_opts は panel が組み立てたものをそのまま素通しする。

    json 系 (live_chat / comments) の埋め込み可否判定は downloader 側。
    """
    sub = {
        "writesubtitles": True,
        "writeautomaticsub": False,
        "subtitleslangs": ["live_chat", "comments"],
        "subtitlesformat": "best",
        "embed": False,
    }
    panel = _panel(format_spec="137+140", subtitle_opts=sub)
    job = build_job_spec("fmt_original", Settings(), panel=panel)
    assert job.subtitle_opts == sub


def test_original_raw_settings_passthrough() -> None:
    """panel.raw_settings は orig_settings として JobSpec に格納される。

    nico_comments 等の lookup に使われる。
    """
    raw = {"nico_comments": {"convert_to_ass": True}}
    panel = _panel(format_spec="137+140", raw_settings=raw)
    job = build_job_spec("fmt_original", Settings(), panel=panel)
    assert job.orig_settings is raw


def test_original_requires_panel() -> None:
    with pytest.raises(ValueError):
        build_job_spec("fmt_original", Settings(), panel=None)


# ── 共通: JobSpec dataclass の不変性 ──────────────────────────────────────


def test_jobspec_frozen() -> None:
    job = build_job_spec("fmt_best_mp4", Settings())
    with pytest.raises(Exception):
        job.format_id = "fmt_mp3"  # type: ignore[misc]


# ── 等価性: 追加・編集・プレイリスト 3 路で同一入力なら同一 JobSpec ───────


def test_same_inputs_produce_same_jobspec_across_call_sites() -> None:
    """A/B の集約効果: 同じ format_id + 同じ Settings → 同じ JobSpec。

    リファクタ前は _add_url / _apply_edit / _enqueue_playlist が
    独自に組み立てており、微妙な挙動差 (mp3_bitrate / embed_thumbnail) が
    あった。build_job_spec 集約後はこれが解消される。
    """
    settings = Settings(
        video_resolution="1080",
        video_container="mp4",
        audio_format="mp3",
        mp3_bitrate="192",
    )
    a = build_job_spec("fmt_720p", settings)
    b = build_job_spec("fmt_720p", settings)
    assert a == b


def test_jobspec_eq() -> None:
    assert JobSpec(
        format_id="fmt_mp3",
        format_spec="bestaudio/best",
        subtitle_opts=None,
        embed_thumbnail=False,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec="mp3",
        mp3_bitrate="192",
        video_container="mp4",
        audio_only=True,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    ) == JobSpec(
        format_id="fmt_mp3",
        format_spec="bestaudio/best",
        subtitle_opts=None,
        embed_thumbnail=False,
        embed_metadata=True,
        embed_chapters=True,
        audio_codec="mp3",
        mp3_bitrate="192",
        video_container="mp4",
        audio_only=True,
        remux_only=False,
        orig_settings=None,
        is_multi_audio=False,
    )


# ── 区間ダウンロード (section_*) ───────────────────────────────────────────


def test_section_defaults_to_none() -> None:
    # 区間引数を渡さなければ全 format_id で None / None / False
    for fmt in ("fmt_best_mp4", "fmt_720p", "fmt_mp3"):
        job = build_job_spec(fmt, Settings())
        assert job.section_start is None
        assert job.section_end is None
        assert job.section_force_keyframes is False


@pytest.mark.parametrize("fmt", ["fmt_best_mp4", "fmt_720p", "fmt_mp3"])
def test_section_passed_through_all_formats(fmt: str) -> None:
    job = build_job_spec(
        fmt,
        Settings(),
        section_start="00:01:30",
        section_end="00:04:00",
        section_force_keyframes=True,
    )
    assert job.section_start == "00:01:30"
    assert job.section_end == "00:04:00"
    assert job.section_force_keyframes is True


def test_section_passed_through_original() -> None:
    job = build_job_spec(
        "fmt_original",
        Settings(),
        panel=_panel(),
        section_start="10",
        section_end="20",
    )
    assert job.section_start == "10"
    assert job.section_end == "20"
    assert job.section_force_keyframes is False
