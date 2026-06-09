"""yt_gui.downloader の `_build_ydl_opts` のテスト。

対応仕様:
- docs/spec/features/download-behavior.md
- docs/spec/features/download-formats.md

`_build_ydl_opts` は `JobSpec` から yt-dlp の `ydl_opts` dict を組み立てる
副作用のないヘルパ。format / postprocessors / 字幕オプションの分岐を
表で網羅する。
"""

from __future__ import annotations

import subprocess

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
    recode_video: bool = False,
    embed_thumbnail: bool = False,
    embed_metadata: bool = True,
    embed_chapters: bool = True,
    subtitle_opts: dict | None = None,
    orig_settings: dict | None = None,
    is_multi_audio: bool = False,
    section_start: str | None = None,
    section_end: str | None = None,
    section_force_keyframes: bool = False,
    ignore_archive: bool = False,
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
        recode_video=recode_video,
        orig_settings=orig_settings,
        is_multi_audio=is_multi_audio,
        section_start=section_start,
        section_end=section_end,
        section_force_keyframes=section_force_keyframes,
        ignore_archive=ignore_archive,
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


def test_recode_video_forces_h264_aac_mp4(downloader, tmp_path) -> None:
    """recode_video=True: FFmpegVideoConvertor を先頭に積み、H.264/AAC を明示し、
    中間コンテナを mkv に固定して必ず mp4 へ再エンコードする。"""
    opts = downloader._build_ydl_opts(
        _job(format_spec="137+140", recode_video=True, video_container="mp4"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    # 中間コンテナを mkv に固定（convertor が ext 一致でスキップしないように）
    assert opts["merge_output_format"] == "mkv"
    # VideoConvertor は postprocessors の先頭
    assert opts["postprocessors"][0]["key"] == "FFmpegVideoConvertor"
    assert opts["postprocessors"][0]["preferedformat"] == "mp4"
    # H.264 / AAC を明示強制（出力ストリームへ適用される videoconvertor キー）
    assert opts["postprocessor_args"]["videoconvertor"] == [
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
    ]


def test_recode_video_pp_order_before_metadata(downloader, tmp_path) -> None:
    """VideoConvertor はメタデータ埋め込みより前に走る。"""
    opts = downloader._build_ydl_opts(
        _job(format_spec="137+140", recode_video=True, video_container="mp4"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert _pp_keys(opts) == ["FFmpegVideoConvertor", "FFmpegMetadata"]


def test_recode_video_allows_thumbnail_embed(downloader, tmp_path) -> None:
    """出力が mp4 なのでサムネ埋め込み可。順序は convertor→metadata→thumbnail。"""
    opts = downloader._build_ydl_opts(
        _job(
            format_spec="137+140",
            recode_video=True,
            video_container="mp4",
            embed_thumbnail=True,
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["writethumbnail"] is True
    assert _pp_keys(opts) == [
        "FFmpegVideoConvertor",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]


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


def test_recode_video_with_subtitle_embed_order(downloader, tmp_path) -> None:
    """再エンコード × 字幕埋め込み: VideoConvertor が先頭で、字幕の
    convert → embed はその後段に並ぶ（spec original-format-panel.md の
    「再エンコード時も字幕埋め込み可」を担保）。"""
    opts = downloader._build_ydl_opts(
        _job(
            format_spec="137+140",
            recode_video=True,
            video_container="mp4",
            subtitle_opts={
                "writesubtitles": True,
                "subtitleslangs": ["en"],
                "subtitlesformat": "srt",
                "embed": True,
            },
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    pp_keys = _pp_keys(opts)
    assert pp_keys[0] == "FFmpegVideoConvertor"
    assert pp_keys.index("FFmpegVideoConvertor") < pp_keys.index(
        "FFmpegSubtitlesConvertor"
    )
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


def test_rate_limit_default_omits_opt(downloader, tmp_path) -> None:
    # 既定 (0 = 無制限) は yt-dlp 既定と同じなので opt を渡さない
    opts = downloader._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "ratelimit" not in opts


def test_rate_limit_passed_when_positive(tmp_path) -> None:
    dl = Downloader(output_dir=str(tmp_path), rate_limit=1024 * 1024)
    opts = dl._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["ratelimit"] == 1024 * 1024


def test_download_archive_default_omits_opt(downloader, tmp_path) -> None:
    # 既定 (パス未設定 = 無効) は opt を渡さない
    opts = downloader._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "download_archive" not in opts


def test_download_archive_passed_when_set(tmp_path) -> None:
    archive = str(tmp_path / "archive.txt")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=archive)
    opts = dl._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["download_archive"] == archive


def test_download_archive_omitted_when_ignore_archive(tmp_path) -> None:
    # アイテム単位の ignore_archive=True なら、アーカイブ有効でも opt を渡さない
    archive = str(tmp_path / "archive.txt")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=archive)
    opts = dl._build_ydl_opts(
        _job(ignore_archive=True),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "download_archive" not in opts


class _FakeYDL:
    """`_resolve_unique_path` 用の最小スタブ。`extract_info` の戻り値を注入する。"""

    _next_info = None  # クラス属性で各テストが差し替える

    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download, extra_info=None):
        return type(self)._next_info

    def in_download_archive(self, info):
        # #93: アーカイブ済みでは extract_info が None を返すため本来呼ばれない。
        # 呼ばれたら AttributeError 再発を検知できるよう記録する。
        _FakeYDL.calls.append("in_download_archive")
        return False

    def prepare_filename(self, info):
        return str(self._stem)


def _patch_fake_ydl(monkeypatch, tmp_path, *, info):
    import yt_gui.downloader as dl_mod

    _FakeYDL._next_info = info
    _FakeYDL._stem = tmp_path / "動画.mp4"
    _FakeYDL.calls = []
    monkeypatch.setattr(dl_mod, "YoutubeDL", _FakeYDL)


def test_resolve_unique_path_skipped_when_archived_info_none(
    tmp_path, monkeypatch
) -> None:
    # #93 回帰: アーカイブ済み動画は extract_info(download=False) が None を返す。
    # in_download_archive(None) を呼ばず DownloadSkipped を送出すること。
    from yt_gui.downloader import DownloadSkipped

    archive = str(tmp_path / "archive.txt")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=archive)
    _patch_fake_ydl(monkeypatch, tmp_path, info=None)

    with pytest.raises(DownloadSkipped):
        dl._resolve_unique_path(
            {}, "https://example.com/v", _job(ignore_archive=False), extra_info=None
        )
    # in_download_archive(None) を呼んでいない（AttributeError を出さない）
    assert _FakeYDL.calls == []


def test_resolve_unique_path_no_skip_when_ignore_archive(tmp_path, monkeypatch) -> None:
    # ignore_archive=True のときは download_archive opt を渡さないため extract_info は
    # 通常どおり info を返す。スキップせず通常のパス解決を行う。
    archive = str(tmp_path / "archive.txt")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=archive)
    _patch_fake_ydl(
        monkeypatch, tmp_path, info={"id": "vid", "extractor_key": "Youtube"}
    )

    stem, ext = dl._resolve_unique_path(
        {}, "https://example.com/v", _job(ignore_archive=True), extra_info=None
    )
    assert ext == ".mp4"


def test_resolve_unique_path_clear_error_when_info_none_not_archive(
    tmp_path, monkeypatch
) -> None:
    # アーカイブ無効で info=None になるのは想定外。AttributeError ではなく
    # 原因の分かる DownloadError を送出すること。
    from yt_dlp.utils import DownloadError

    dl = Downloader(output_dir=str(tmp_path))  # アーカイブ無効
    _patch_fake_ydl(monkeypatch, tmp_path, info=None)

    with pytest.raises(DownloadError):
        dl._resolve_unique_path({}, "https://example.com/v", _job(), extra_info=None)


def test_filter_unarchived_entries_disabled_returns_all(tmp_path) -> None:
    dl = Downloader(output_dir=str(tmp_path))  # アーカイブ無効
    entries = [
        {"url": "u1", "title": "t1", "id": "id1", "ie_key": "Youtube"},
        {"url": "u2", "title": "t2", "id": "id2", "ie_key": "Youtube"},
    ]
    assert dl.filter_unarchived_entries(entries) == entries


def test_filter_unarchived_entries_excludes_recorded(tmp_path) -> None:
    archive = tmp_path / "archive.txt"
    # yt-dlp の記録形式は "{extractor_lower} {id}"
    archive.write_text("youtube id1\n", encoding="utf-8")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=str(archive))
    entries = [
        {"url": "u1", "title": "t1", "id": "id1", "ie_key": "Youtube"},
        {"url": "u2", "title": "t2", "id": "id2", "ie_key": "Youtube"},
    ]
    result = dl.filter_unarchived_entries(entries)
    assert [e["id"] for e in result] == ["id2"]


def test_filter_unarchived_entries_keeps_entries_without_id(tmp_path) -> None:
    archive = tmp_path / "archive.txt"
    archive.write_text("youtube id1\n", encoding="utf-8")
    dl = Downloader(output_dir=str(tmp_path), download_archive_path=str(archive))
    # id / ie_key 欠落エントリは判定できないため残す（ベストエフォート）
    entries = [{"url": "u1", "title": "t1", "id": None, "ie_key": None}]
    assert dl.filter_unarchived_entries(entries) == entries


def _build(dl: Downloader, job: JobSpec, tmp_path) -> dict:
    return dl._build_ydl_opts(
        job,
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )


def _pp(opts: dict, key: str) -> dict:
    return next(pp for pp in opts["postprocessors"] if pp["key"] == key)


def test_sponsorblock_disabled_adds_no_pp(downloader, tmp_path) -> None:
    # 既定 (mode="") では SponsorBlock 関連 PP を一切積まない
    opts = _build(downloader, _job(), tmp_path)
    assert "SponsorBlock" not in _pp_keys(opts)
    assert "ModifyChapters" not in _pp_keys(opts)


def test_sponsorblock_empty_categories_adds_no_pp(tmp_path) -> None:
    dl = Downloader(
        output_dir=str(tmp_path), sponsorblock_mode="mark", sponsorblock_categories=[]
    )
    opts = _build(dl, _job(), tmp_path)
    assert "SponsorBlock" not in _pp_keys(opts)
    assert "ModifyChapters" not in _pp_keys(opts)


def test_sponsorblock_unknown_categories_filtered_out(tmp_path) -> None:
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="mark",
        sponsorblock_categories=["sponsor", "bogus"],
    )
    opts = _build(dl, _job(), tmp_path)
    assert _pp(opts, "SponsorBlock")["categories"] == {"sponsor"}


def test_sponsorblock_mark_adds_pps_without_removal(tmp_path) -> None:
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="mark",
        sponsorblock_categories=["sponsor", "selfpromo"],
    )
    opts = _build(dl, _job(), tmp_path)

    sb = _pp(opts, "SponsorBlock")
    assert sb["categories"] == {"sponsor", "selfpromo"}
    assert sb["when"] == "after_filter"

    modify = _pp(opts, "ModifyChapters")
    assert modify["remove_sponsor_segments"] == set()
    # mark を可視化するためチャプター埋め込みが有効化される
    assert _pp(opts, "FFmpegMetadata")["add_chapters"] is True


def test_sponsorblock_remove_sets_remove_segments(tmp_path) -> None:
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="remove",
        sponsorblock_categories=["sponsor"],
    )
    opts = _build(dl, _job(), tmp_path)

    assert _pp(opts, "SponsorBlock")["categories"] == {"sponsor"}
    assert _pp(opts, "ModifyChapters")["remove_sponsor_segments"] == {"sponsor"}


def test_sponsorblock_modifychapters_runs_before_metadata(tmp_path) -> None:
    # ModifyChapters は FFmpegMetadata より前に並ぶ必要がある
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="mark",
        sponsorblock_categories=["sponsor"],
    )
    opts = _build(dl, _job(), tmp_path)
    keys = _pp_keys(opts)
    assert keys.index("ModifyChapters") < keys.index("FFmpegMetadata")


def test_sponsorblock_audio_modifychapters_after_extract(tmp_path) -> None:
    # 音声抽出時は FFmpegExtractAudio の後に ModifyChapters が来る
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="remove",
        sponsorblock_categories=["sponsor"],
    )
    opts = _build(
        dl,
        _job(format_id="fmt_mp3", audio_only=True, audio_codec="mp3"),
        tmp_path,
    )
    keys = _pp_keys(opts)
    assert keys.index("FFmpegExtractAudio") < keys.index("ModifyChapters")


def test_sponsorblock_mark_adds_metadata_pp_when_absent(tmp_path) -> None:
    # メタデータ / チャプター埋め込みが無効でも mark 用に FFmpegMetadata を補う
    dl = Downloader(
        output_dir=str(tmp_path),
        sponsorblock_mode="mark",
        sponsorblock_categories=["sponsor"],
    )
    opts = _build(dl, _job(embed_metadata=False, embed_chapters=False), tmp_path)
    meta = _pp(opts, "FFmpegMetadata")
    assert meta["add_chapters"] is True
    assert meta["add_metadata"] is False
    keys = _pp_keys(opts)
    assert keys.index("ModifyChapters") < keys.index("FFmpegMetadata")


# ── ダウンロードの中断（DownloadCancelled） ──────────────────────────────


def test_progress_hook_raises_download_cancelled_when_requested(downloader) -> None:
    from yt_dlp.utils import DownloadCancelled

    downloader.status_callback = lambda *a, **k: None
    downloader.request_cancel()
    with pytest.raises(DownloadCancelled):
        downloader._progress_hook({"status": "downloading", "downloaded_bytes": 1})


def test_progress_hook_normal_when_not_requested(downloader) -> None:
    calls = []
    downloader.status_callback = lambda *a, **k: calls.append(a)
    # 中断要求なし → 例外を投げず通常の進捗通知
    downloader._progress_hook(
        {"status": "downloading", "downloaded_bytes": 5, "total_bytes": 10}
    )
    assert calls  # status_callback が呼ばれている


def test_cleanup_partial_files_removes_only_temp_files(downloader, tmp_path) -> None:
    stem = str(tmp_path / "動画")
    temp = [
        tmp_path / "動画.mp4.part",
        tmp_path / "動画.f137.mp4",
        tmp_path / "動画.f140.m4a.part",
        tmp_path / "動画.ytdl",
        tmp_path / "動画.mp4.part-Frag0",
    ]
    keep = [
        tmp_path / "動画.mp4",  # 完成済み最終ファイル
        tmp_path / "動画.info.json",  # サイドカー
        tmp_path / "別の動画.mp4.part",  # 別アイテム
    ]
    for p in temp + keep:
        p.write_text("x")

    downloader._cleanup_partial_files(stem)

    for p in temp:
        assert not p.exists(), f"{p.name} は削除されるべき"
    for p in keep:
        assert p.exists(), f"{p.name} は残すべき"


def test_cleanup_partial_files_removes_subtitle_sidecars(downloader, tmp_path) -> None:
    stem = str(tmp_path / "動画")
    subs = [
        tmp_path / "動画.en.srt",
        tmp_path / "動画.ja.vtt",
        tmp_path / "動画.en.ass",
        tmp_path / "動画.en.json3",
        tmp_path / "動画.live_chat.json",  # YouTube ライブチャット
        tmp_path / "動画.comments.json",  # ニコニコ動画コメント
    ]
    keep = [
        tmp_path / "動画.mp4",  # 完成済み最終ファイル
        tmp_path / "動画.info.json",  # メタデータ（字幕ではない）
        tmp_path / "動画.jpg",  # サムネイル
    ]
    for p in subs + keep:
        p.write_text("x")

    downloader._cleanup_partial_files(stem)

    for p in subs:
        assert not p.exists(), f"{p.name} は削除されるべき"
    for p in keep:
        assert p.exists(), f"{p.name} は残すべき"


def test_download_video_cleans_up_and_reraises_on_cancel(downloader, tmp_path) -> None:
    from yt_dlp.utils import DownloadCancelled

    downloader.status_callback = lambda *a, **k: None
    stem = str(tmp_path / "動画")
    part = tmp_path / "動画.mp4.part"
    part.write_text("x")

    downloader._resolve_unique_path = lambda *a, **k: (stem, ".mp4")

    def _raise(*a, **k):
        raise DownloadCancelled()

    downloader._run_download = _raise

    job = _job()
    with pytest.raises(DownloadCancelled):
        downloader.download_video("https://example.com/v", job)
    assert not part.exists()


def test_download_video_clears_previous_cancel_request(downloader, tmp_path) -> None:
    downloader.status_callback = lambda *a, **k: None
    downloader.request_cancel()  # 前回の中断要求が残っている状態を模す

    seen = {}
    downloader._resolve_unique_path = lambda *a, **k: (str(tmp_path / "v"), ".mp4")

    def _run(*a, **k):
        seen["cancel_set"] = downloader._cancel_requested.is_set()

    downloader._run_download = _run
    downloader.download_video("https://example.com/v", _job())
    assert seen["cancel_set"] is False  # ジョブ開始時にクリアされている


# ── 区間ダウンロード（フル取得 → ローカル切り出し） ─────────────────────────


def test_section_omits_native_download_ranges(downloader, tmp_path) -> None:
    """方針 A ではフル取得後にローカルで切り出すため、yt-dlp の
    download_ranges / force_keyframes_at_cuts は一切渡さない。"""
    opts = downloader._build_ydl_opts(
        _job(section_start="00:01:30", section_end="00:04:00"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "download_ranges" not in opts
    assert "force_keyframes_at_cuts" not in opts


def test_build_cut_cmd_copy_mode_uses_input_seek_and_copy() -> None:
    cmd = Downloader._build_cut_cmd(
        "ffmpeg", "in.mp4", "out.mp4", "00:01:00", "00:01:05", force_keyframes=False
    )
    # 入力側シーク（-i より前に -ss/-to）+ stream copy
    assert cmd == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        "00:01:00",
        "-to",
        "00:01:05",
        "-i",
        "in.mp4",
        "-c",
        "copy",
        "out.mp4",
    ]


def test_build_cut_cmd_force_keyframes_uses_output_seek_and_reencode() -> None:
    cmd = Downloader._build_cut_cmd(
        "ffmpeg", "in.mp4", "out.mp4", "10", "20", force_keyframes=True
    )
    # 出力側シーク（-i の後に -ss/-to）・-c copy なし（再エンコード）
    assert cmd == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        "in.mp4",
        "-ss",
        "10",
        "-to",
        "20",
        "out.mp4",
    ]
    assert "copy" not in cmd


def test_cut_section_replaces_original_on_success(downloader, tmp_path, monkeypatch):
    downloader.status_callback = lambda *a, **k: None
    # CI にはバンドル ffmpeg が無いため、実在するダミーを指す
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("")
    downloader._ffmpeg_path = str(ffmpeg)
    stem = str(tmp_path / "動画")
    infile = tmp_path / "動画.mp4"
    infile.write_text("ORIGINAL")

    captured = {}

    def _fake_run(cmd, **kwargs):
        # ffmpeg の代わりに out ファイルを生成
        captured["cmd"] = cmd
        with open(cmd[-1], "w") as f:
            f.write("CUT")

        class _R:
            returncode = 0

        return _R()

    monkeypatch.setattr("yt_gui.downloader.subprocess.run", _fake_run)

    downloader._cut_section(
        stem, ".mp4", _job(section_start="00:00:01", section_end="00:00:02")
    )

    assert infile.read_text() == "CUT"  # 原本が切り出し結果で置換された
    assert not (tmp_path / "動画.section.mp4").exists()  # 一時ファイルは残らない


def test_cut_section_keeps_full_on_failure(downloader, tmp_path, monkeypatch):
    downloader.status_callback = lambda *a, **k: None
    logs = []
    downloader.log_callback = logs.append
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("")
    downloader._ffmpeg_path = str(ffmpeg)
    stem = str(tmp_path / "動画")
    infile = tmp_path / "動画.mp4"
    infile.write_text("ORIGINAL")

    import subprocess as _sp

    def _fail_run(cmd, **kwargs):
        raise _sp.CalledProcessError(1, cmd, stderr="boom")

    monkeypatch.setattr("yt_gui.downloader.subprocess.run", _fail_run)

    downloader._cut_section(stem, ".mp4", _job(section_start="1", section_end="2"))

    assert infile.read_text() == "ORIGINAL"  # 失敗時はフル動画を保持
    assert any("boom" in m for m in logs)


def test_download_video_invokes_cut_section_when_section_set(downloader, tmp_path):
    downloader.status_callback = lambda *a, **k: None
    downloader._resolve_unique_path = lambda *a, **k: (str(tmp_path / "v"), ".mp4")
    downloader._run_download = lambda *a, **k: None

    calls = []
    downloader._cut_section = lambda stem, ext, job: calls.append((stem, ext, job))

    job = _job(section_start="00:00:01", section_end="00:00:02")
    downloader.download_video("https://example.com/v", job)
    assert len(calls) == 1

    calls.clear()
    downloader.download_video("https://example.com/v", _job())  # 区間なし
    assert calls == []


# ── fetch_formats / fetch_title_or_entries（YoutubeDL スタブ） ───────────────


class _StubYDL:
    """`extract_info` が固定 info を返す YoutubeDL スタブ。"""

    info: dict | None = {}

    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False, extra_info=None):
        return type(self).info


def _patch_stub_ydl(monkeypatch, info):
    import yt_gui.downloader as dl_mod

    _StubYDL.info = info
    monkeypatch.setattr(dl_mod, "YoutubeDL", _StubYDL)


def test_fetch_formats_classifies_video_audio_and_muxed(
    downloader, monkeypatch
) -> None:
    info = {
        "title": "T",
        "formats": [
            # 映像のみ（音声なし）
            {
                "format_id": "137",
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "none",
                "height": 1080,
                "width": 1920,
                "tbr": 4000,
            },
            # 音声のみ
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a",
                "abr": 128,
                "language": "en",
            },
            # muxed（映像 + 音声）
            {
                "format_id": "18",
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "height": 360,
                "width": 640,
            },
            # codec 情報なし → muxed 救済
            {"format_id": "raw", "ext": "flv"},
        ],
    }
    _patch_stub_ydl(monkeypatch, info)

    result = downloader.fetch_formats("u")

    video_ids = {fid for (_lbl, fid, _ha) in result["video"]}
    audio_ids = {fid for (_lbl, fid) in result["audio"]}
    has_audio = {fid: ha for (_lbl, fid, ha) in result["video"]}

    assert video_ids == {"137", "18", "raw"}
    assert audio_ids == {"140"}
    assert has_audio["137"] is False  # 音声なし映像
    assert has_audio["18"] is True  # muxed
    assert has_audio["raw"] is True  # codec 不明 → muxed 救済
    assert result["title"] == "T"
    # video_resolutions は width/height のある映像のみ
    assert result["video_resolutions"]["137"] == (1920, 1080)
    assert result["video_resolutions"]["18"] == (640, 360)
    assert "raw" not in result["video_resolutions"]


def test_fetch_formats_subtitle_classification(downloader, monkeypatch) -> None:
    info = {
        "title": "T",
        "formats": [],
        "language": "en",
        "subtitles": {
            "en": [{"ext": "vtt"}],
            "live_chat": [{"ext": "json"}],
            "comments": [{"ext": "json"}],
        },
        "automatic_captions": {
            "en": [{"ext": "vtt"}],  # 主言語 → 残す（auto=True）
            "fr": [{"ext": "vtt"}],  # 非主言語かつ手動に無い → 除外
            "live_chat": [{"ext": "json"}],  # json 専用 → auto からは除外
        },
    }
    _patch_stub_ydl(monkeypatch, info)

    result = downloader.fetch_formats("u")
    langs = [(lang, auto) for (_lbl, lang, auto) in result["subtitles"]]

    assert ("en", False) in langs  # 手動字幕
    assert ("live_chat", False) in langs  # json 専用（手動扱い）
    assert ("comments", False) in langs  # json 専用（手動扱い）
    assert ("en", True) in langs  # 自動字幕（主言語）
    assert all(lang != "fr" for (lang, _a) in langs)  # 非主言語は除外
    # live_chat は自動字幕としては重複追加されない（手動扱いの 1 件のみ）
    assert sum(1 for (lang, _a) in langs if lang == "live_chat") == 1


def test_fetch_title_or_entries_single(downloader, monkeypatch) -> None:
    info = {"title": "Video", "webpage_url": "https://x/v", "thumbnail": "t.jpg"}
    _patch_stub_ydl(monkeypatch, info)

    assert downloader.fetch_title_or_entries("u") == {
        "type": "single",
        "url": "https://x/v",
        "title": "Video",
        "thumbnail_url": "t.jpg",
    }


def test_fetch_title_or_entries_playlist_skips_empty_and_falls_back(
    downloader, monkeypatch
) -> None:
    info = {
        "title": "PL",
        "entries": [
            {
                "webpage_url": "https://x/1",
                "title": "A",
                "thumbnail": None,
                "id": "1",
                "ie_key": "Youtube",
            },
            None,  # 空エントリはスキップ
            {
                "url": "https://x/2",
                "title": None,
                "id": None,
            },  # title は url にフォールバック
            {"title": "no-url"},  # url 無しはスキップ
        ],
    }
    _patch_stub_ydl(monkeypatch, info)

    result = downloader.fetch_title_or_entries("u")
    assert result["type"] == "playlist"
    assert result["title"] == "PL"
    assert [e["url"] for e in result["entries"]] == ["https://x/1", "https://x/2"]
    assert result["entries"][1]["title"] == "https://x/2"  # タイトル欠落 → url


def test_fetch_title_or_entries_empty_info_returns_url(downloader, monkeypatch) -> None:
    _patch_stub_ydl(monkeypatch, None)

    assert downloader.fetch_title_or_entries("theurl") == {
        "type": "single",
        "url": "theurl",
        "title": "theurl",
        "thumbnail_url": None,
    }


# ── missing_dependencies / cookies / base opts / logger ────────────────────


def test_missing_dependencies_all_present(downloader, monkeypatch) -> None:
    monkeypatch.setattr("yt_gui.downloader.os.path.isfile", lambda p: True)
    assert downloader.missing_dependencies() == []


def test_missing_dependencies_reports_absent(downloader, monkeypatch) -> None:
    monkeypatch.setattr("yt_gui.downloader.os.path.isfile", lambda p: False)
    assert downloader.missing_dependencies() == ["ffmpeg", "ffprobe", "deno"]


def test_cookies_opts_browser_takes_precedence() -> None:
    assert Downloader._cookies_opts("c.txt", "firefox") == {
        "cookiesfrombrowser": ("firefox",)
    }


def test_cookies_opts_file_only() -> None:
    assert Downloader._cookies_opts("c.txt", None) == {"cookies": "c.txt"}


def test_cookies_opts_none() -> None:
    assert Downloader._cookies_opts(None, None) == {}


def test_base_ydl_opts_includes_proxy_logger_and_cookies(tmp_path) -> None:
    logs: list[str] = []
    dl = Downloader(
        output_dir=str(tmp_path),
        proxy_url="http://p:8080",
        log_callback=logs.append,
    )
    opts = dl._base_ydl_opts(cookies_path="c.txt")
    assert opts["proxy"] == "http://p:8080"
    assert "logger" in opts
    assert opts["cookies"] == "c.txt"
    assert "ejs:github" in opts["remote_components"]


def test_base_ydl_opts_omits_proxy_and_logger_by_default(tmp_path) -> None:
    dl = Downloader(output_dir=str(tmp_path))  # proxy/log_callback なし
    opts = dl._base_ydl_opts()
    assert "proxy" not in opts
    assert "logger" not in opts


def test_ytdlp_logger_filters_debug_and_progress() -> None:
    from yt_gui.downloader import _YtdlpLogger

    msgs: list[str] = []
    lg = _YtdlpLogger(msgs.append)
    lg.debug("[debug] internal")  # スキップ
    lg.debug("[download]  45.2% of 10MiB")  # 進捗 → スキップ
    lg.debug("plain debug-routed info")  # 通す
    lg.info("info message")  # 通す
    lg.info("")  # 空 → 無視
    lg.warning("careful")
    lg.error("boom")

    assert "plain debug-routed info" in msgs
    assert "info message" in msgs
    assert "⚠️ careful" in msgs
    assert "❌ boom" in msgs
    assert not any("[debug]" in m or "45.2%" in m for m in msgs)


# ── _progress_hook の各分岐 ────────────────────────────────────────────────


def test_progress_hook_finished_reports_100(downloader) -> None:
    seen: list[tuple[str, float]] = []
    downloader.status_callback = lambda msg, pct: seen.append((msg, pct))
    downloader._progress_hook({"status": "finished", "filename": "/p/動画.mp4"})
    assert seen and seen[-1][1] == 100


def test_progress_hook_downloading_with_total_reports_percent(downloader) -> None:
    seen: list[tuple[str, float]] = []
    downloader.status_callback = lambda msg, pct: seen.append((msg, pct))
    downloader._progress_hook(
        {"status": "downloading", "total_bytes": 200, "downloaded_bytes": 50}
    )
    assert seen and seen[-1][1] == pytest.approx(25.0)


def test_progress_hook_downloading_without_total_reports_zero(downloader) -> None:
    seen: list[tuple[str, float]] = []
    downloader.status_callback = lambda msg, pct: seen.append((msg, pct))
    downloader._progress_hook({"status": "downloading", "downloaded_bytes": 50})
    assert seen and seen[-1][1] == 0


def test_progress_hook_error_and_other_status(downloader) -> None:
    seen: list[tuple[str, float]] = []
    downloader.status_callback = lambda msg, pct: seen.append((msg, pct))
    downloader._progress_hook({"status": "error"})
    downloader._progress_hook({"status": "extracting"})
    assert len(seen) == 2


# ── ニコ動コメント / 区間カットのガード分岐（ファイル/バイナリ不在 → ログのみ） ──


def test_convert_nico_comments_skips_when_json_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    logs: list[str] = []
    downloader.log_callback = logs.append
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._convert_nico_comments_to_ass(str(tmp_path / "stem"), {})
    assert called["run"] is False
    assert len(logs) == 1  # 警告ログのみ


def test_cut_section_skips_when_infile_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    logs: list[str] = []
    downloader.log_callback = logs.append
    downloader.status_callback = lambda *a: None
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._cut_section(
        str(tmp_path / "nope"), ".mp4", _job(section_start="0", section_end="1")
    )
    assert called["run"] is False
    assert len(logs) == 1


def test_embed_nico_comments_skips_when_video_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    logs: list[str] = []
    downloader.log_callback = logs.append
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._embed_nico_comments_into_mkv(str(tmp_path / "nope"), ".mp4", {})
    assert called["run"] is False
    assert len(logs) == 1


# ── ハードサブ焼きこみ (#120 Phase 2) ──────────────────────────────────────


def test_escape_ass_filter_value_wraps_and_escapes() -> None:
    # 通常のベース名は単一引用符で囲むだけ
    assert Downloader._escape_ass_filter_value("v.comments.ass") == "'v.comments.ass'"
    # 単一引用符は \' にエスケープ
    assert Downloader._escape_ass_filter_value("a'b.ass") == "'a\\'b.ass'"
    # バックスラッシュは \\ にエスケープ
    assert Downloader._escape_ass_filter_value("a\\b.ass") == "'a\\\\b.ass'"


def test_build_hardsub_cmd_uses_ass_filter_and_h264_aac() -> None:
    cmd = Downloader._build_hardsub_cmd(
        "/bin/ffmpeg",
        "/out/動画.mp4",
        "'動画.comments.ass'",
        "/out/動画.hardsub.mp4",
    )
    assert cmd == [
        "/bin/ffmpeg",
        "-y",
        "-i",
        "/out/動画.mp4",
        "-vf",
        "ass='動画.comments.ass'",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "/out/動画.hardsub.mp4",
    ]


def test_burn_nico_comments_skips_when_video_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    logs: list[str] = []
    downloader.log_callback = logs.append
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._burn_nico_comments_into_video(str(tmp_path / "nope"), ".mp4", {})
    assert called["run"] is False
    assert len(logs) == 1


def test_burn_nico_comments_skips_when_ass_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    (tmp_path / "v.mp4").write_text("x")  # 動画はあるが ASS が無い
    logs: list[str] = []
    downloader.log_callback = logs.append
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._burn_nico_comments_into_video(str(tmp_path / "v"), ".mp4", {})
    assert called["run"] is False
    assert len(logs) == 1


def test_burn_nico_comments_invokes_ffmpeg_with_cwd_and_basename(
    downloader, tmp_path, monkeypatch
) -> None:
    (tmp_path / "動画.mp4").write_text("v")
    (tmp_path / "動画.comments.ass").write_text("a")
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text("")
    downloader._ffmpeg_path = str(fake_ffmpeg)
    downloader.log_callback = lambda m: None

    captured: dict = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")

        class _R:
            pass

        return _R()

    monkeypatch.setattr("yt_gui.downloader.subprocess.run", _fake_run)

    downloader._burn_nico_comments_into_video(str(tmp_path / "動画"), ".mp4", {})

    # filtergraph のパス問題回避: cwd を動画ディレクトリにしてベース名のみ渡す
    assert captured["cwd"] == str(tmp_path)
    vf_idx = captured["cmd"].index("-vf")
    assert captured["cmd"][vf_idx + 1] == "ass='動画.comments.ass'"
    assert captured["cmd"][-1].endswith("動画.hardsub.mp4")


def test_burn_nico_comments_skips_when_no_ffmpeg(
    downloader, tmp_path, monkeypatch
) -> None:
    """ffmpeg バイナリ不在では subprocess を呼ばず非致命ログのみ。"""
    (tmp_path / "v.mp4").write_text("x")
    (tmp_path / "v.comments.ass").write_text("a")
    downloader._ffmpeg_path = str(tmp_path / "no-ffmpeg")  # 存在しない
    logs: list[str] = []
    downloader.log_callback = logs.append
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._burn_nico_comments_into_video(str(tmp_path / "v"), ".mp4", {})
    assert called["run"] is False
    assert len(logs) == 1


def test_burn_nico_comments_ffmpeg_failure_is_non_fatal(
    downloader, tmp_path, monkeypatch
) -> None:
    """ffmpeg が非 0 終了しても例外を投げず、警告ログのみ（非致命）。"""
    (tmp_path / "v.mp4").write_text("x")
    (tmp_path / "v.comments.ass").write_text("a")
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text("")
    downloader._ffmpeg_path = str(fake_ffmpeg)
    logs: list[str] = []
    downloader.log_callback = logs.append

    def _raise(*a, **k):
        raise subprocess.CalledProcessError(1, "ffmpeg", stderr="boom")

    monkeypatch.setattr("yt_gui.downloader.subprocess.run", _raise)

    # 例外が伝播しないこと
    downloader._burn_nico_comments_into_video(str(tmp_path / "v"), ".mp4", {})
    assert any("boom" in m for m in logs)


# ── 追加: 純ロジックの未カバー分 ────────────────────────────────────────────


def test_strip_json_only_subs_pp_removes_json_langs() -> None:
    from yt_gui.downloader import _StripJsonOnlySubsBeforeEmbedPP

    pp = _StripJsonOnlySubsBeforeEmbedPP()
    info = {"requested_subtitles": {"en": {}, "live_chat": {}, "comments": {}}}
    _ret, out = pp.run(info)
    assert set(out["requested_subtitles"]) == {"en"}


def test_strip_json_only_subs_pp_noop_without_json_langs() -> None:
    from yt_gui.downloader import _StripJsonOnlySubsBeforeEmbedPP

    pp = _StripJsonOnlySubsBeforeEmbedPP()
    info = {"requested_subtitles": {"en": {}, "ja": {}}}
    _ret, out = pp.run(info)
    assert set(out["requested_subtitles"]) == {"en", "ja"}


def test_resolve_unique_path_audio_extraction_uses_codec_ext(
    downloader, tmp_path, monkeypatch
) -> None:
    _patch_fake_ydl(monkeypatch, tmp_path, info={"id": "v"})
    _stem, ext = downloader._resolve_unique_path(
        {},
        "https://example.com/v",
        _job(format_id="fmt_mp3", audio_only=True, audio_codec="mp3"),
        extra_info=None,
    )
    assert ext == ".mp3"


def test_resolve_unique_path_appends_suffix_on_collision(
    downloader, tmp_path, monkeypatch
) -> None:
    _patch_fake_ydl(monkeypatch, tmp_path, info={"id": "v"})
    (tmp_path / "動画.mp4").write_text("x")  # 既存ファイルで衝突を起こす
    opts: dict = {}
    stem, ext = downloader._resolve_unique_path(
        opts, "https://example.com/v", _job(remux_only=True), extra_info=None
    )
    assert ext == ".mp4"
    assert stem.endswith("動画 (1)")
    assert opts["outtmpl"].endswith("動画 (1).%(ext)s")


def test_cut_section_skips_when_ffmpeg_missing(
    downloader, tmp_path, monkeypatch
) -> None:
    (tmp_path / "動画.mp4").write_text("x")  # infile は存在
    downloader._ffmpeg_path = str(tmp_path / "no-ffmpeg")  # ffmpeg は不在
    logs: list[str] = []
    downloader.log_callback = logs.append
    downloader.status_callback = lambda *a: None
    called = {"run": False}
    monkeypatch.setattr(
        "yt_gui.downloader.subprocess.run",
        lambda *a, **k: called.__setitem__("run", True),
    )
    downloader._cut_section(
        str(tmp_path / "動画"), ".mp4", _job(section_start="0", section_end="1")
    )
    assert called["run"] is False
    assert len(logs) == 1
