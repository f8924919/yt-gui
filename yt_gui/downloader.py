import os
import re
import sys

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.common import PostProcessor

from . import get_resource_base
from .formats import FORMAT_SPECS, build_720p_spec, build_best_spec
from .i18n import t
from .output_template import DEFAULT_PLAYLIST_TEMPLATE, DEFAULT_VIDEO_TEMPLATE
from .utils import strip_ansi

_LIVE_CHAT_LANG = "live_chat"

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


class _StripLiveChatBeforeEmbedPP(PostProcessor):
    """live_chat 字幕は json 専用で ffmpeg では変換も埋め込みもできないため、
    後段の FFmpegSubtitlesConvertor / FFmpegEmbedSubtitle が処理対象として
    見ないよう `requested_subtitles` から外す。json ファイルは既に
    ダウンロード済みなので、サイドカーとしてそのまま残る。"""

    def run(self, info):
        subs = info.get("requested_subtitles") or {}
        if _LIVE_CHAT_LANG in subs:
            info["requested_subtitles"] = {
                k: v for k, v in subs.items() if k != _LIVE_CHAT_LANG
            }
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
    ):
        self.output_dir = output_dir
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.video_resolution = video_resolution
        self.mp3_bitrate = mp3_bitrate
        self.output_template_video = output_template_video
        self.output_template_playlist = output_template_playlist

        _ext = ".exe" if sys.platform == "win32" else ""
        base = get_resource_base()
        bin_dir = base if getattr(sys, "_MEIPASS", None) else os.path.join(base, "bin")
        self._deno_path = os.path.join(bin_dir, f"deno{_ext}")
        self._ffmpeg_path = os.path.join(bin_dir, "ffmpeg", f"ffmpeg{_ext}")
        self._ffprobe_path = os.path.join(bin_dir, "ffmpeg", f"ffprobe{_ext}")

        os.makedirs(self.output_dir, exist_ok=True)

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
            if not formats or lang == _LIVE_CHAT_LANG:
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

        return {
            "title": info.get("title", ""),
            "video": video_formats,
            "audio": audio_formats,
            "subtitles": subtitle_list,
        }

    def download_video(
        self,
        url,
        format_id,
        cookies_path=None,
        format_spec=None,
        subtitle_opts=None,
        mp3_bitrate_override=None,
        embed_thumbnail=False,
        remux_only=False,
        output_dir_override=None,
        cookies_browser=None,
        audio_codec: str = "mp3",
        embed_metadata: bool = False,
        embed_chapters: bool = False,
        video_container: str = "mp4",
        playlist_title: str | None = None,
        playlist_index: int | None = None,
        audio_only: bool = False,
    ):
        if format_spec is not None:
            spec = format_spec
            _, is_audio = FORMAT_SPECS.get(format_id, ("best/best", False))
        elif format_id == "fmt_best_mp4":
            spec = build_best_spec(video_container)
            is_audio = False
        elif format_id == "fmt_720p":
            spec = build_720p_spec(self.video_resolution, video_container)
            is_audio = False
        else:
            spec, is_audio = FORMAT_SPECS.get(format_id, ("best/best", False))

        # オリジナル形式で音声のみが選ばれている場合は音声抽出経路へ
        if format_id == "fmt_original" and audio_only:
            is_audio = True

        out_dir = output_dir_override or self.output_dir
        os.makedirs(out_dir, exist_ok=True)

        is_playlist = playlist_title is not None
        template = (
            self.output_template_playlist if is_playlist else self.output_template_video
        )
        extra_info: dict | None = None
        if is_playlist:
            extra_info = {
                "playlist_title": playlist_title,
                "playlist": playlist_title,
                "playlist_index": playlist_index,
            }

        ydl_opts = {
            "format": spec,
            "outtmpl": os.path.join(out_dir, template),
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "color": "no_color",
            **self._base_ydl_opts(cookies_path, cookies_browser),
        }

        if is_audio:
            pp: dict = {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_codec,
            }
            if audio_codec == "mp3":
                pp["preferredquality"] = mp3_bitrate_override or self.mp3_bitrate
            ydl_opts["postprocessors"] = [pp]
            if embed_metadata or embed_chapters:
                ydl_opts["postprocessors"].append(
                    {
                        "key": "FFmpegMetadata",
                        "add_metadata": embed_metadata,
                        "add_chapters": embed_chapters,
                    }
                )
            if embed_thumbnail and audio_codec == "mp3":
                ydl_opts["writethumbnail"] = True
                ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})
        else:
            if not remux_only:
                ydl_opts["merge_output_format"] = video_container
            if embed_metadata or embed_chapters:
                ydl_opts.setdefault("postprocessors", []).append(
                    {
                        "key": "FFmpegMetadata",
                        "add_metadata": embed_metadata,
                        "add_chapters": embed_chapters,
                    }
                )
            if (
                embed_thumbnail
                and not remux_only
                and video_container in _THUMBNAIL_EMBED_CONTAINERS
            ):
                ydl_opts["writethumbnail"] = True
                ydl_opts.setdefault("postprocessors", []).append(
                    {"key": "EmbedThumbnail"}
                )

        if subtitle_opts:
            embed = subtitle_opts.get("embed", False)
            for key in (
                "writesubtitles",
                "writeautomaticsub",
                "subtitleslangs",
                "subtitlesformat",
            ):
                if key in subtitle_opts:
                    ydl_opts[key] = subtitle_opts[key]
            if embed:
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

        msg = t("dl_fetching")
        self.status_callback(msg, 0)
        if self.log_callback:
            self.log_callback(msg)

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, extra_info=extra_info)
            raw_path = ydl.prepare_filename(info)

        stem, raw_ext = os.path.splitext(raw_path)
        if is_audio:
            final_ext = f".{audio_codec}"
        elif remux_only:
            final_ext = raw_ext
        elif "+" in spec:
            final_ext = f".{video_container}"
        else:
            final_ext = raw_ext

        if os.path.exists(stem + final_ext):
            n = 1
            while os.path.exists(f"{stem} ({n}){final_ext}"):
                n += 1
            ydl_opts["outtmpl"] = f"{stem} ({n}).%(ext)s"

        # live_chat を埋め込み対象に含む場合は、convert/embed が live_chat.json を
        # 触らないように先にストリップ PP を実行する。
        sub_langs = (subtitle_opts or {}).get("subtitleslangs") or []
        needs_strip_live_chat = (
            (subtitle_opts or {}).get("embed", False)
            and _LIVE_CHAT_LANG in sub_langs
        )

        with YoutubeDL(ydl_opts) as ydl:
            if needs_strip_live_chat:
                ydl.add_post_processor(
                    _StripLiveChatBeforeEmbedPP(), when="post_process"
                )
                # 末尾に追加された PP を先頭へ移動 (convert/embed の前で実行させる)
                pp_list = ydl._pps["post_process"]
                pp_list.insert(0, pp_list.pop())
            ydl.extract_info(url, download=True, extra_info=extra_info)
