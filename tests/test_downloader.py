"""yt_gui.downloader の `_build_ydl_opts` のテスト。

対応仕様:
- docs/spec/features/download-behavior.md
- docs/spec/features/download-formats.md

`_build_ydl_opts` は `JobSpec` から yt-dlp の `ydl_opts` dict を組み立てる
副作用のないヘルパ。format / postprocessors / 字幕オプションの分岐を
表で網羅する。
"""

from __future__ import annotations

import pytest

from yt_gui.downloader import Downloader
from yt_gui.job_spec import JobSpec


def _job(
    *,
    format_id: str = "fmt_best_mp4",
    format_spec: str = "bestvideo+bestaudio/best",
    audio_codec: str = "mp3",
    mp3_bitrate: str | None = None,
    video_container: str = "mp4",
    audio_only: bool = False,
    remux_only: bool = False,
    embed_thumbnail: bool = False,
    embed_metadata: bool = True,
    embed_chapters: bool = True,
    subtitle_opts: dict | None = None,
    orig_settings: dict | None = None,
    is_multi_audio: bool = False,
) -> JobSpec:
    return JobSpec(
        format_id=format_id,
        format_spec=format_spec,
        subtitle_opts=subtitle_opts,
        embed_thumbnail=embed_thumbnail,
        embed_metadata=embed_metadata,
        embed_chapters=embed_chapters,
        audio_codec=audio_codec,
        mp3_bitrate=mp3_bitrate,
        video_container=video_container,
        audio_only=audio_only,
        remux_only=remux_only,
        orig_settings=orig_settings,
        is_multi_audio=is_multi_audio,
    )


@pytest.fixture
def downloader(tmp_path):
    return Downloader(output_dir=str(tmp_path))


def _pp_keys(opts: dict) -> list[str]:
    return [pp["key"] for pp in opts.get("postprocessors", [])]


def test_video_mp4_uses_merge_format_and_metadata(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(format_spec="137+140", video_container="mp4"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["format"] == "137+140"
    assert opts["merge_output_format"] == "mp4"
    assert _pp_keys(opts) == ["FFmpegMetadata"]
    assert opts["postprocessors"][0]["add_metadata"] is True
    assert opts["postprocessors"][0]["add_chapters"] is True
    assert "writethumbnail" not in opts


def test_remux_only_skips_merge_output_format(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(remux_only=True, embed_thumbnail=True),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    # remux_only は merge_output_format も thumbnail 埋め込みも適用しない
    assert "merge_output_format" not in opts
    assert "writethumbnail" not in opts
    assert "EmbedThumbnail" not in _pp_keys(opts)


def test_video_embed_thumbnail_supported_container(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(embed_thumbnail=True, video_container="mp4"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["writethumbnail"] is True
    assert "EmbedThumbnail" in _pp_keys(opts)


def test_video_embed_thumbnail_unsupported_container_skipped(
    downloader, tmp_path
) -> None:
    opts = downloader._build_ydl_opts(
        _job(embed_thumbnail=True, video_container="webm"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "writethumbnail" not in opts
    assert "EmbedThumbnail" not in _pp_keys(opts)


def test_audio_mp3_extracts_with_bitrate(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(
            format_id="fmt_mp3",
            audio_only=True,
            audio_codec="mp3",
            mp3_bitrate="320",
            embed_thumbnail=True,
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    pps = opts["postprocessors"]
    assert pps[0]["key"] == "FFmpegExtractAudio"
    assert pps[0]["preferredcodec"] == "mp3"
    assert pps[0]["preferredquality"] == "320"
    assert "FFmpegMetadata" in _pp_keys(opts)
    assert "EmbedThumbnail" in _pp_keys(opts)
    assert opts["writethumbnail"] is True
    assert "merge_output_format" not in opts


def test_audio_flac_no_bitrate(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(audio_only=True, audio_codec="flac", embed_thumbnail=True),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    pps = opts["postprocessors"]
    assert pps[0]["key"] == "FFmpegExtractAudio"
    assert pps[0]["preferredcodec"] == "flac"
    assert "preferredquality" not in pps[0]
    # FLAC は mp3 専用の thumbnail 埋め込み経路に入らない
    assert "EmbedThumbnail" not in _pp_keys(opts)
    assert "writethumbnail" not in opts


def test_multi_audio_sets_allow_flag(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(is_multi_audio=True),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["allow_multiple_audio_streams"] is True


def test_subtitle_embed_adds_convert_and_embed_pps(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(
            subtitle_opts={
                "writesubtitles": True,
                "writeautomaticsub": False,
                "subtitleslangs": ["en"],
                "subtitlesformat": "best",
                "embed": True,
            }
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["writesubtitles"] is True
    assert opts["writeautomaticsub"] is False
    assert opts["subtitleslangs"] == ["en"]
    assert opts["subtitlesformat"] == "best"

    pp_keys = _pp_keys(opts)
    convert_pp = next(
        pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegSubtitlesConvertor"
    )
    # "best" は埋め込み不可なので "srt" にフォールバック
    assert convert_pp["format"] == "srt"
    # convert は embed の前に置く
    assert pp_keys.index("FFmpegSubtitlesConvertor") < pp_keys.index(
        "FFmpegEmbedSubtitle"
    )


def test_subtitle_embed_preserves_explicit_format(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(
            subtitle_opts={
                "subtitleslangs": ["ja"],
                "subtitlesformat": "vtt",
                "embed": True,
            }
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    convert_pp = next(
        pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegSubtitlesConvertor"
    )
    assert convert_pp["format"] == "vtt"


def test_subtitle_no_embed_skips_convert_and_embed(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(subtitle_opts={"subtitleslangs": ["en"], "embed": False}),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    pp_keys = _pp_keys(opts)
    assert "FFmpegSubtitlesConvertor" not in pp_keys
    assert "FFmpegEmbedSubtitle" not in pp_keys


def test_playlist_outtmpl_uses_playlist_template(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=True,
        cookies_path=None,
        cookies_browser=None,
    )

    # デフォルトのプレイリストテンプレートはサブフォルダ構造を含む
    assert "%(playlist_title)s" in opts["outtmpl"]


def test_no_metadata_no_chapters_skips_ffmpeg_metadata_pp(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(embed_metadata=False, embed_chapters=False),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "FFmpegMetadata" not in _pp_keys(opts)


def test_concurrent_fragments_default_omits_opt(downloader, tmp_path) -> None:
    # 既定 (N=1) は yt-dlp 既定と同じなので opt を渡さない
    opts = downloader._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "concurrent_fragment_downloads" not in opts


def test_concurrent_fragments_passed_when_gt_one(tmp_path) -> None:
    dl = Downloader(output_dir=str(tmp_path), concurrent_fragments=4)
    opts = dl._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["concurrent_fragment_downloads"] == 4
