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
    section_start: str | None = None,
    section_end: str | None = None,
    section_force_keyframes: bool = False,
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
        section_start=section_start,
        section_end=section_end,
        section_force_keyframes=section_force_keyframes,
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


# ── 区間ダウンロード (download_ranges) ─────────────────────────────────────


def test_download_sections_default_omits_opts(downloader, tmp_path) -> None:
    # 区間未指定 (両方 None) のときは download_ranges / force_keyframes を渡さない
    opts = downloader._build_ydl_opts(
        _job(),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert "download_ranges" not in opts
    assert "force_keyframes_at_cuts" not in opts


def test_download_sections_sets_download_ranges(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(section_start="00:01:30", section_end="00:04:00"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    # download_ranges は callable (yt_dlp.utils.download_range_func の戻り値)
    assert callable(opts["download_ranges"])
    # 既定では force_keyframes_at_cuts は付かない
    assert "force_keyframes_at_cuts" not in opts

    # 解決された区間 (秒) を info_dict 経由で検証する
    ranges = list(opts["download_ranges"]({"duration": 600}, None))
    assert len(ranges) == 1
    assert ranges[0]["start_time"] == 90.0
    assert ranges[0]["end_time"] == 240.0


def test_download_sections_accepts_mm_ss_and_seconds(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(section_start="90", section_end="4:00"),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    ranges = list(opts["download_ranges"]({"duration": 600}, None))
    assert ranges[0]["start_time"] == 90.0
    assert ranges[0]["end_time"] == 240.0


def test_download_sections_force_keyframes_when_enabled(downloader, tmp_path) -> None:
    opts = downloader._build_ydl_opts(
        _job(
            section_start="00:00:10",
            section_end="00:00:20",
            section_force_keyframes=True,
        ),
        out_dir=str(tmp_path),
        is_playlist=False,
        cookies_path=None,
        cookies_browser=None,
    )

    assert opts["force_keyframes_at_cuts"] is True


def test_download_video_sets_ffmpeg_location_contextvar(downloader, tmp_path) -> None:
    """区間 DL の事前チェック (FFmpegFD.available、downloader 非依存) のため、
    download_video はバンドル ffmpeg のパスを contextvar に設定する。"""
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

    downloader.status_callback = lambda *a, **k: None
    downloader._resolve_unique_path = lambda *a, **k: (str(tmp_path / "v"), ".mp4")

    seen = {}

    def _run(*a, **k):
        seen["loc"] = FFmpegPostProcessor._ffmpeg_location.get()

    downloader._run_download = _run
    downloader.download_video("https://example.com/v", _job())

    assert seen["loc"] == downloader._ffmpeg_path
