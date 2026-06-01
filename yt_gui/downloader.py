import os
import re
import subprocess
import sys

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.common import PostProcessor

from . import get_resource_base
from .i18n import t
from .job_spec import JobSpec
from .output_template import DEFAULT_PLAYLIST_TEMPLATE, DEFAULT_VIDEO_TEMPLATE
from .settings import SPONSORBLOCK_CATEGORIES
from .utils import strip_ansi

_LIVE_CHAT_LANG = "live_chat"
_COMMENTS_LANG = "comments"
_JSON_ONLY_SUB_LANGS = frozenset({_LIVE_CHAT_LANG, _COMMENTS_LANG})

# SponsorBlock でチャプター化される区間のタイトル（yt-dlp CLI の既定値と同じ）
_SPONSORBLOCK_CHAPTER_TITLE = "[SponsorBlock]: %(category_names)l"

_DISPLAY_SUB_EXTS = frozenset({"srt", "vtt", "ttml", "ass", "ssa"})
_THUMBNAIL_EMBED_CONTAINERS = frozenset(
    {"mp3", "mkv", "mka", "ogg", "opus", "flac", "m4a", "mp4", "m4v", "mov"}
)
_DOWNLOAD_PROGRESS_RE = re.compile(r"\[download\]\s+\d")


class _YtdlpLogger:
    """yt-dlp logger that routes significant messages to app's log_callback.

    yt-dlp sends info-level messages through debug() without a '[debug] ' prefix.
    We skip actual debug messages (prefixed '[debug] ') and download progress lines
    (e.g. '[download]  45.2% of ...') so only meaningful events reach the log.
    """

    def __init__(self, callback):
        self._cb = callback

    def debug(self, msg):
        if msg.startswith("[debug] ") or _DOWNLOAD_PROGRESS_RE.match(msg):
            return
        self._cb(strip_ansi(msg))

    def info(self, msg):
        if msg:
            self._cb(strip_ansi(msg))

    def warning(self, msg):
        self._cb(f"⚠️ {strip_ansi(msg)}")

    def error(self, msg):
        self._cb(f"❌ {strip_ansi(msg)}")


class _StripJsonOnlySubsBeforeEmbedPP(PostProcessor):
    """json 専用字幕 (live_chat / ニコニコ動画 comments) は ffmpeg では
    変換も埋め込みもできないため、後段の FFmpegSubtitlesConvertor /
    FFmpegEmbedSubtitle が処理対象として見ないよう `requested_subtitles`
    から外す。json ファイルは既にダウンロード済みなので、サイドカーとして
    そのまま残る。"""

    def run(self, info):
        subs = info.get("requested_subtitles") or {}
        filtered = {k: v for k, v in subs.items() if k not in _JSON_ONLY_SUB_LANGS}
        if len(filtered) != len(subs):
            info["requested_subtitles"] = filtered
        return [], info


class Downloader:
    def __init__(
        self,
        output_dir="downloads",
        status_callback=None,
        video_resolution="720",
        mp3_bitrate="192",
        log_callback=None,
        output_template_video: str = DEFAULT_VIDEO_TEMPLATE,
        output_template_playlist: str = DEFAULT_PLAYLIST_TEMPLATE,
        proxy_url: str = "",
        concurrent_fragments: int = 1,
        sponsorblock_mode: str = "",
        sponsorblock_categories: list[str] | None = None,
    ):
        self.output_dir = output_dir
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.video_resolution = video_resolution
        self.mp3_bitrate = mp3_bitrate
        self.output_template_video = output_template_video
        self.output_template_playlist = output_template_playlist
        self.proxy_url = proxy_url
        self.concurrent_fragments = concurrent_fragments
        self.sponsorblock_mode = sponsorblock_mode
        self.sponsorblock_categories = sponsorblock_categories or []

        _ext = ".exe" if sys.platform == "win32" else ""
        base = get_resource_base()
        bin_dir = base if getattr(sys, "_MEIPASS", None) else os.path.join(base, "bin")
        self._deno_path = os.path.join(bin_dir, f"deno{_ext}")
        self._ffmpeg_path = os.path.join(bin_dir, "ffmpeg", f"ffmpeg{_ext}")
        self._ffprobe_path = os.path.join(bin_dir, "ffmpeg", f"ffprobe{_ext}")
        self._danmaku2ass_path = os.path.join(bin_dir, f"danmaku2ass{_ext}")

        os.makedirs(self.output_dir, exist_ok=True)

    def missing_dependencies(self) -> list[str]:
        """同梱バイナリのうち存在しないものの名前を返す。

        返り値: `['ffmpeg', 'ffprobe', 'deno']` のサブセット。
        空リストならすべて揃っている。`app.py` 起動時の依存チェックや
        `_embed_nico_comments_into_mkv` 内で利用される。
        """
        missing: list[str] = []
        if not self._ffmpeg_path or not os.path.isfile(self._ffmpeg_path):
            missing.append("ffmpeg")
        if not self._ffprobe_path or not os.path.isfile(self._ffprobe_path):
            missing.append("ffprobe")
        if not self._deno_path or not os.path.isfile(self._deno_path):
            missing.append("deno")
        return missing

    def _progress_hook(self, d):
        if self.status_callback is None:
            return

        status = d["status"]
        if status == "finished":
            filename = d.get("filename", "Unknown File")
            msg = t("dl_done").format(filename=os.path.basename(filename))
            self.status_callback(msg, 100)
            if self.log_callback:
                self.log_callback(msg)
        elif status == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes", 0)
            if total_bytes:
                percent = downloaded_bytes / total_bytes * 100
                speed = d.get("_speed_str", "N/A")
                eta = d.get("_eta_str", "N/A")
                self.status_callback(
                    t("dl_progress").format(
                        percent=d.get("_percent_str", "0.0%"),
                        speed=speed,
                        eta=eta,
                    ),
                    percent,
                )
            else:
                self.status_callback(
                    t("dl_processing").format(percent=d.get("_percent_str", "")), 0
                )
        elif status == "error":
            msg = t("dl_error")
            self.status_callback(msg, 0)
            if self.log_callback:
                self.log_callback(msg)
        else:
            self.status_callback(t("dl_status").format(status=status), 0)

    @staticmethod
    def _cookies_opts(cookies_path=None, cookies_browser=None) -> dict:
        if cookies_browser:
            return {"cookiesfrombrowser": (cookies_browser,)}
        if cookies_path:
            return {"cookies": cookies_path}
        return {}

    def _base_ydl_opts(self, cookies_path=None, cookies_browser=None) -> dict:
        opts = {
            "js_runtimes": {"deno": {"path": self._deno_path}},
            "ffmpeg_location": self._ffmpeg_path,
            "remote_components": ["ejs:github"],
            **self._cookies_opts(cookies_path, cookies_browser),
        }
        if self.proxy_url:
            opts["proxy"] = self.proxy_url
        if self.log_callback:
            opts["logger"] = _YtdlpLogger(self.log_callback)
        return opts

    def fetch_title_or_entries(
        self, url, cookies_path=None, cookies_browser=None
    ) -> dict:
        """Return {'type': 'single', 'url': str, 'title': str} or
        {'type': 'playlist', 'entries': [{'url': str, 'title': str}, ...]}"""
        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            **self._base_ydl_opts(cookies_path, cookies_browser),
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {"type": "single", "url": url, "title": url, "thumbnail_url": None}

        entries = info.get("entries")
        if entries is not None:
            result = []
            for entry in entries:
                if not entry:
                    continue
                entry_url = entry.get("webpage_url") or entry.get("url")
                if not entry_url:
                    continue
                result.append(
                    {
                        "url": entry_url,
                        "title": entry.get("title") or entry_url,
                        "thumbnail_url": entry.get("thumbnail"),
                    }
                )
            return {
                "type": "playlist",
                "entries": result,
                "title": info.get("title", ""),
            }

        title = info.get("title") or url
        actual_url = info.get("webpage_url") or url
        return {
            "type": "single",
            "url": actual_url,
            "title": title,
            "thumbnail_url": info.get("thumbnail"),
        }

    def fetch_formats(self, url, cookies_path=None, cookies_browser=None):
        ydl_opts = {
            "quiet": True,
            "noplaylist": True,
            # 一部の抽出器 (例: NiconicoIE) は `InfoExtractor.extract_subtitles` を
            # 経由して字幕を info dict に詰める。このメソッドは `writesubtitles` /
            # `listsubtitles` のいずれかが立っていないと `_get_subtitles` を呼ばず
            # `{}` を返すため、フラグを立てない限りニコニコ動画の `comments` lang
            # などが UI 上の字幕リストに出てこない。YouTube extractor は
            # `info['subtitles']` を直接代入するため影響を受けないが、ゲート経由の
            # 抽出器のために本フラグを必ず立てる。`download=False` ではファイル
            # 書き出しは発生しないので安全。
            "writesubtitles": True,
            **self._base_ydl_opts(cookies_path, cookies_browser),
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        raw = sorted(
            info.get("formats", []),
            key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
            reverse=True,
        )

        video_formats: list[tuple[str, str, bool]] = []
        audio_formats: list[tuple[str, str]] = []
        for f in raw:
            fid = f.get("format_id", "?")
            ext = f.get("ext", "?")
            vcodec = f.get("vcodec") or "none"
            acodec = f.get("acodec") or "none"
            has_video = vcodec != "none"
            has_audio = acodec != "none"
            # vcodec/acodec が一切未設定の format は muxed メディアとして扱う
            # （xvideos など、抽出器が直接 URL だけを返す場合の救済）
            if not has_video and not has_audio:
                has_video = True
                has_audio = True

            if has_video:
                height = f.get("height")
                res = f"{height}p" if height else "?"
                tbr = f.get("tbr") or f.get("vbr")
                brate = f" – {tbr:.0f}kbps" if tbr else ""
                marker = " ★" if has_audio else ""
                vcodec_label = vcodec if vcodec != "none" else ext
                label = f"{res} {vcodec_label} ({ext}) [{fid}]{brate}{marker}"
                video_formats.append((label, fid, has_audio))
            elif has_audio:
                abr = f.get("abr") or f.get("tbr")
                brate = f" – {abr:.0f}kbps" if abr else ""
                lang = f.get("language") or ""
                lang_tag = f" [{lang}]" if lang else ""
                label = f"{acodec} ({ext}) [{fid}]{brate}{lang_tag}"
                audio_formats.append((label, fid))

        # Subtitle extraction
        subtitles_raw = info.get("subtitles") or {}
        auto_captions_raw = info.get("automatic_captions") or {}
        primary_lang = (info.get("language") or "").lower()
        manual_langs = frozenset(subtitles_raw.keys())

        subtitle_list: list[tuple[str, str, bool]] = []

        for lang, formats in sorted(subtitles_raw.items()):
            if not formats:
                continue
            if lang == _LIVE_CHAT_LANG:
                # ライブチャット (json 専用、埋め込み不可) は専用ラベルで提示
                subtitle_list.append(
                    (f"{lang} – {t('orig_sub_live_chat_name')} [json]", lang, False)
                )
                continue
            if lang == _COMMENTS_LANG:
                # ニコニコ動画コメント (json 専用、埋め込み不可) は専用ラベルで提示
                subtitle_list.append(
                    (
                        f"{lang} – {t('orig_sub_nico_comments_name')} [json]",
                        lang,
                        False,
                    )
                )
                continue
            exts = (
                ", ".join(
                    dict.fromkeys(
                        f["ext"] for f in formats if f.get("ext") in _DISPLAY_SUB_EXTS
                    )
                )
                or "best"
            )
            name = next((f.get("name") for f in formats if f.get("name")), lang)
            subtitle_list.append((f"{lang} – {name} [{exts}]", lang, False))

        for lang, formats in sorted(auto_captions_raw.items()):
            if not formats or lang in _JSON_ONLY_SUB_LANGS:
                continue
            # Limit auto captions to primary language family when known
            if primary_lang:
                lang_base = lang.split("-")[0].lower()
                if lang_base != primary_lang.split("-")[0] and lang not in manual_langs:
                    continue
            exts = (
                ", ".join(
                    dict.fromkeys(
                        f["ext"] for f in formats if f.get("ext") in _DISPLAY_SUB_EXTS
                    )
                )
                or "best"
            )
            name = next((f.get("name") for f in formats if f.get("name")), lang)
            label = f"{lang} – {name} {t('orig_sub_auto_marker')} [{exts}]"
            subtitle_list.append((label, lang, True))

        # 映像 ID → (width, height) (フェーズ 3: コメント ASS 解像度の自動追従用)
        video_resolutions: dict[str, tuple[int, int]] = {}
        for f in raw:
            fid = f.get("format_id")
            w = f.get("width")
            h = f.get("height")
            if fid and isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                video_resolutions[fid] = (w, h)

        return {
            "title": info.get("title", ""),
            "video": video_formats,
            "audio": audio_formats,
            "subtitles": subtitle_list,
            "video_resolutions": video_resolutions,
        }

    def download_video(
        self,
        url: str,
        job: JobSpec,
        cookies_path: str | None = None,
        *,
        output_dir_override: str | None = None,
        cookies_browser: str | None = None,
        playlist_title: str | None = None,
        playlist_index: int | None = None,
    ):
        out_dir = output_dir_override or self.output_dir
        os.makedirs(out_dir, exist_ok=True)

        is_playlist = playlist_title is not None
        extra_info: dict | None = None
        if is_playlist:
            extra_info = {
                "playlist_title": playlist_title,
                "playlist": playlist_title,
                "playlist_index": playlist_index,
            }

        ydl_opts = self._build_ydl_opts(
            job,
            out_dir=out_dir,
            is_playlist=is_playlist,
            cookies_path=cookies_path,
            cookies_browser=cookies_browser,
        )

        msg = t("dl_fetching")
        self.status_callback(msg, 0)
        if self.log_callback:
            self.log_callback(msg)

        effective_stem, final_ext = self._resolve_unique_path(
            ydl_opts, url, job, extra_info=extra_info
        )

        self._run_download(ydl_opts, url, job, extra_info=extra_info)

        nico_comments_opts = (job.orig_settings or {}).get("nico_comments")
        sub_langs = (job.subtitle_opts or {}).get("subtitleslangs") or []
        if (
            nico_comments_opts
            and nico_comments_opts.get("convert_to_ass")
            and _COMMENTS_LANG in sub_langs
        ):
            self._convert_nico_comments_to_ass(effective_stem, nico_comments_opts)

            if nico_comments_opts.get("embed_to_mkv") and not job.is_audio_extraction:
                self._embed_nico_comments_into_mkv(
                    effective_stem, final_ext, nico_comments_opts
                )

    def _build_ydl_opts(
        self,
        job: JobSpec,
        *,
        out_dir: str,
        is_playlist: bool,
        cookies_path: str | None,
        cookies_browser: str | None,
    ) -> dict:
        """`JobSpec` から `ydl_opts` dict を組み立てる。

        - 音声抽出 / 映像ダウンロードでそれぞれ必要な postprocessors を積む
        - 字幕埋め込み時は convert + embed PP を最後に積む
        """
        template = (
            self.output_template_playlist if is_playlist else self.output_template_video
        )

        ydl_opts: dict = {
            "format": job.format_spec,
            "outtmpl": os.path.join(out_dir, template),
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "color": "no_color",
            **self._base_ydl_opts(cookies_path, cookies_browser),
        }

        # フラグメント分割される動画（DASH/HLS）でのみ高速化に寄与する。
        # N=1 は yt-dlp 既定と同じなので、>1 のときだけ明示的に渡す。
        if self.concurrent_fragments and self.concurrent_fragments > 1:
            ydl_opts["concurrent_fragment_downloads"] = self.concurrent_fragments

        if job.is_multi_audio:
            ydl_opts["allow_multiple_audio_streams"] = True

        if job.is_audio_extraction:
            self._append_audio_postprocessors(ydl_opts, job)
        else:
            self._append_video_postprocessors(ydl_opts, job)

        if job.subtitle_opts:
            self._append_subtitle_options(ydl_opts, job.subtitle_opts)

        self._append_sponsorblock_postprocessors(ydl_opts)

        return ydl_opts

    def _append_sponsorblock_postprocessors(self, ydl_opts: dict) -> None:
        """SponsorBlock の mark / remove ポストプロセッサを積む。

        - `sponsorblock_mode` が空、または有効カテゴリが 0 件のときは何もしない。
        - `SponsorBlock` PP は `after_filter` フェーズで対象区間を検出してチャプタ化する
          （リスト内での位置は実行順に影響しないため末尾に追加する）。
        - `ModifyChapters` PP は `FFmpegMetadata` / `EmbedThumbnail` より前
          （post_process フェーズ）で動く必要があるため、それらの直前へ挿入する。
          `FFmpegExtractAudio` はリスト先頭にあるため自動的に前段になる。
        - mark を出力ファイルに反映するにはチャプター埋め込みが要るので、
          `FFmpegMetadata` の `add_chapters` を有効化する（yt-dlp CLI が
          `--sponsorblock-mark` 指定時に `addchapters` を自動 ON にするのと同じ）。
        """
        mode = self.sponsorblock_mode
        if mode not in ("mark", "remove"):
            return
        categories = [
            c for c in self.sponsorblock_categories if c in SPONSORBLOCK_CATEGORIES
        ]
        if not categories:
            return

        category_set = set(categories)
        remove_set = category_set if mode == "remove" else set()
        pps: list[dict] = ydl_opts.setdefault("postprocessors", [])

        if mode == "mark":
            self._ensure_chapters_embedded(pps)

        modify_pp = {
            "key": "ModifyChapters",
            "remove_sponsor_segments": remove_set,
            "sponsorblock_chapter_title": _SPONSORBLOCK_CHAPTER_TITLE,
            "force_keyframes": False,
        }
        anchor = next(
            (
                i
                for i, pp in enumerate(pps)
                if pp.get("key") in ("FFmpegMetadata", "EmbedThumbnail")
            ),
            len(pps),
        )
        pps.insert(anchor, modify_pp)

        pps.append(
            {
                "key": "SponsorBlock",
                "categories": category_set,
                "when": "after_filter",
            }
        )

    @staticmethod
    def _ensure_chapters_embedded(pps: list[dict]) -> None:
        """既存の `FFmpegMetadata` PP に `add_chapters=True` を立てる。
        無い場合はチャプター埋め込み専用の `FFmpegMetadata` を追加する。"""
        for pp in pps:
            if pp.get("key") == "FFmpegMetadata":
                pp["add_chapters"] = True
                return
        pps.append(
            {"key": "FFmpegMetadata", "add_metadata": False, "add_chapters": True}
        )

    def _append_audio_postprocessors(self, ydl_opts: dict, job: JobSpec) -> None:
        audio_codec = job.audio_codec
        pp: dict = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_codec,
        }
        if audio_codec == "mp3":
            pp["preferredquality"] = job.mp3_bitrate or self.mp3_bitrate
        ydl_opts["postprocessors"] = [pp]
        if job.embed_metadata or job.embed_chapters:
            ydl_opts["postprocessors"].append(
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": job.embed_metadata,
                    "add_chapters": job.embed_chapters,
                }
            )
        if job.embed_thumbnail and audio_codec == "mp3":
            ydl_opts["writethumbnail"] = True
            ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})

    def _append_video_postprocessors(self, ydl_opts: dict, job: JobSpec) -> None:
        if not job.remux_only:
            ydl_opts["merge_output_format"] = job.video_container
        if job.embed_metadata or job.embed_chapters:
            ydl_opts.setdefault("postprocessors", []).append(
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": job.embed_metadata,
                    "add_chapters": job.embed_chapters,
                }
            )
        if (
            job.embed_thumbnail
            and not job.remux_only
            and job.video_container in _THUMBNAIL_EMBED_CONTAINERS
        ):
            ydl_opts["writethumbnail"] = True
            ydl_opts.setdefault("postprocessors", []).append({"key": "EmbedThumbnail"})

    @staticmethod
    def _append_subtitle_options(ydl_opts: dict, subtitle_opts: dict) -> None:
        for key in (
            "writesubtitles",
            "writeautomaticsub",
            "subtitleslangs",
            "subtitlesformat",
        ):
            if key in subtitle_opts:
                ydl_opts[key] = subtitle_opts[key]
        if subtitle_opts.get("embed", False):
            # YouTube Live など JSON (json3) しか配信されないケースでは
            # FFmpegEmbedSubtitle が "JSON subtitles cannot be embedded" を
            # 出すため、埋め込み前に SRT/VTT へ変換しておく。
            preferred = subtitle_opts.get("subtitlesformat") or "best"
            convert_to = "srt" if preferred in ("best", None) else preferred
            ydl_opts.setdefault("postprocessors", []).append(
                {"key": "FFmpegSubtitlesConvertor", "format": convert_to}
            )
            ydl_opts.setdefault("postprocessors", []).append(
                {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False}
            )

    def _resolve_unique_path(
        self,
        ydl_opts: dict,
        url: str,
        job: JobSpec,
        *,
        extra_info: dict | None,
    ) -> tuple[str, str]:
        """同名ファイル衝突を避けるため `(stem, final_ext)` を予測し、
        必要なら `outtmpl` を ` (N)` 付きに上書きする。

        戻り値: `(effective_stem, final_ext)` — ニコニコ動画コメントの
        後処理がファイル名を組み立てるのに使う。
        """
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, extra_info=extra_info)
            raw_path = ydl.prepare_filename(info)

        stem, raw_ext = os.path.splitext(raw_path)
        if job.is_audio_extraction:
            final_ext = f".{job.audio_codec}"
        elif job.remux_only:
            final_ext = raw_ext
        elif "+" in job.format_spec:
            final_ext = f".{job.video_container}"
        else:
            final_ext = raw_ext

        effective_stem = stem
        if os.path.exists(stem + final_ext):
            n = 1
            while os.path.exists(f"{stem} ({n}){final_ext}"):
                n += 1
            ydl_opts["outtmpl"] = f"{stem} ({n}).%(ext)s"
            effective_stem = f"{stem} ({n})"

        return effective_stem, final_ext

    def _run_download(
        self,
        ydl_opts: dict,
        url: str,
        job: JobSpec,
        *,
        extra_info: dict | None,
    ) -> None:
        """ydl を起動してダウンロードを実行する。

        json 専用字幕 (live_chat / ニコニコ動画 comments) が埋め込み対象に
        含まれるときは convert/embed が json を触らないように strip PP を
        先頭に挿入する。
        """
        sub_langs = (job.subtitle_opts or {}).get("subtitleslangs") or []
        needs_strip_json_only_subs = bool(
            job.subtitle_opts and job.subtitle_opts.get("embed", False)
        ) and any(lang in _JSON_ONLY_SUB_LANGS for lang in sub_langs)

        with YoutubeDL(ydl_opts) as ydl:
            if needs_strip_json_only_subs:
                ydl.add_post_processor(
                    _StripJsonOnlySubsBeforeEmbedPP(), when="post_process"
                )
                # yt-dlp 内部 API 依存: `add_post_processor` は常に末尾追加で
                # ある一方、convert/embed の前で strip を走らせる必要がある。
                # `params["postprocessors"]` は dict 形式のみ受け付けるため
                # custom PP クラスをそこに混ぜることもできない。yt-dlp の
                # バージョン更新時にここが壊れる可能性があるので注意。
                pp_list = ydl._pps["post_process"]
                pp_list.insert(0, pp_list.pop())
            ydl.extract_info(url, download=True, extra_info=extra_info)

    def _convert_nico_comments_to_ass(self, stem: str, opts: dict) -> None:
        """ニコニコ動画コメント JSON を danmaku2ass で ASS に変換する。

        失敗・バイナリ欠如はいずれも非致命としてログのみ。
        """
        json_path = f"{stem}.{_COMMENTS_LANG}.json"
        ass_path = f"{stem}.{_COMMENTS_LANG}.ass"

        if not os.path.exists(json_path):
            if self.log_callback:
                base = os.path.basename(json_path)
                self.log_callback(t("warn_nico_ass_skip_no_json").format(filename=base))
            return
        if not os.path.exists(self._danmaku2ass_path):
            if self.log_callback:
                self.log_callback(t("warn_danmaku2ass_missing"))
            return

        cmd = [
            self._danmaku2ass_path,
            "-o",
            ass_path,
            "-s",
            f"{opts.get('resolution_w', 1920)}x{opts.get('resolution_h', 1080)}",
            "-f",
            "NiconicoYtdlpJson2",
            "-dm",
            str(opts.get("duration_sec", 8.0)),
            "-fs",
            str(opts.get("font_size", 32)),
            "-a",
            str(opts.get("opacity", 0.8)),
            json_path,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if self.log_callback:
                self.log_callback(
                    t("status_danmaku2ass_created").format(
                        filename=os.path.basename(ass_path)
                    )
                )
        except subprocess.CalledProcessError as e:
            if self.log_callback:
                err = strip_ansi(e.stderr or e.stdout or str(e)).strip()
                self.log_callback(t("warn_danmaku2ass_failed").format(error=err))
        except FileNotFoundError:
            # _danmaku2ass_path が exists() を通ったあとに消えた等のレース
            if self.log_callback:
                self.log_callback(t("warn_danmaku2ass_missing"))

    def _embed_nico_comments_into_mkv(
        self, stem: str, final_ext: str, opts: dict
    ) -> None:
        """動画 + コメント ASS をソフトサブで結合した MKV を別ファイルとして生成する。

        元動画は触らず、`{stem}.with-comments.mkv` を新規作成する。
        ffmpeg は再エンコードなしの stream copy (`-c copy -c:s ass`)。
        失敗・前提ファイル不在はいずれも非致命としてログのみ。
        """
        video_path = f"{stem}{final_ext}"
        ass_path = f"{stem}.{_COMMENTS_LANG}.ass"

        if not os.path.exists(video_path):
            if self.log_callback:
                base = os.path.basename(video_path)
                self.log_callback(t("warn_nico_mkv_skip_missing").format(filename=base))
            return
        if not os.path.exists(ass_path):
            if self.log_callback:
                base = os.path.basename(ass_path)
                self.log_callback(t("warn_nico_mkv_skip_missing").format(filename=base))
            return
        if not os.path.exists(self._ffmpeg_path):
            if self.log_callback:
                self.log_callback(t("warn_nico_mkv_skip_no_ffmpeg"))
            return

        out_path = f"{stem}.with-comments.mkv"
        if os.path.exists(out_path):
            n = 1
            while os.path.exists(f"{stem}.with-comments ({n}).mkv"):
                n += 1
            out_path = f"{stem}.with-comments ({n}).mkv"

        cmd = [
            self._ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-i",
            ass_path,
            "-map",
            "0",
            "-map",
            "1",
            "-c",
            "copy",
            "-c:s",
            "ass",
            "-metadata:s:s:0",
            f"title={t('nico_group_title')}",
            "-metadata:s:s:0",
            "language=jpn",
            out_path,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if self.log_callback:
                self.log_callback(
                    t("status_nico_mkv_created").format(
                        filename=os.path.basename(out_path)
                    )
                )
        except subprocess.CalledProcessError as e:
            if self.log_callback:
                err = strip_ansi(e.stderr or e.stdout or str(e)).strip()
                self.log_callback(t("warn_nico_mkv_failed").format(error=err))
