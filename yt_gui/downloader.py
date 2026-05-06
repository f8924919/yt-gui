import os
import sys
from yt_dlp import YoutubeDL

from .formats import FORMAT_SPECS
from .i18n import t
from . import get_resource_base

_DISPLAY_SUB_EXTS = frozenset({'srt', 'vtt', 'ttml', 'ass', 'ssa'})
_SKIP_AUTO_LANGS = frozenset({'live_chat'})


class Downloader:
    def __init__(self, output_dir="downloads", status_callback=None,
                 video_resolution="720", mp3_bitrate="192"):
        self.output_dir = output_dir
        self.status_callback = status_callback
        self.video_resolution = video_resolution
        self.mp3_bitrate = mp3_bitrate

        _ext = '.exe' if sys.platform == 'win32' else ''
        base = get_resource_base()
        bin_dir = base if getattr(sys, '_MEIPASS', None) else os.path.join(base, 'bin')
        self._deno_path = os.path.join(bin_dir, f'deno{_ext}')
        self._ffmpeg_path = os.path.join(bin_dir, 'ffmpeg', f'ffmpeg{_ext}')

        os.makedirs(self.output_dir, exist_ok=True)

    def _progress_hook(self, d):
        if self.status_callback is None:
            return

        status = d['status']
        if status == 'finished':
            filename = d.get('filename', 'Unknown File')
            self.status_callback(t("dl_done").format(filename=os.path.basename(filename)), 100)
        elif status == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                percent = downloaded_bytes / total_bytes * 100
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                self.status_callback(
                    t("dl_progress").format(
                        percent=d.get('_percent_str', '0.0%'),
                        speed=speed,
                        eta=eta,
                    ),
                    percent,
                )
            else:
                self.status_callback(t("dl_processing").format(percent=d.get('_percent_str', '')), 0)
        elif status == 'error':
            self.status_callback(t("dl_error"), 0)
        else:
            self.status_callback(t("dl_status").format(status=status), 0)

    def fetch_title_or_entries(self, url, cookies_path=None) -> dict:
        """Return {'type': 'single', 'url': str, 'title': str} or
                  {'type': 'playlist', 'entries': [{'url': str, 'title': str}, ...]}"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'js_runtimes': {'deno': {'path': self._deno_path}},
            'ffmpeg_location': self._ffmpeg_path,
            'remote_components': ['ejs:github'],
            'cookies': cookies_path,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {'type': 'single', 'url': url, 'title': url}

        entries = info.get('entries')
        if entries is not None:
            result = []
            for entry in entries:
                if not entry:
                    continue
                entry_url = entry.get('webpage_url') or entry.get('url')
                if not entry_url:
                    continue
                result.append({
                    'url': entry_url,
                    'title': entry.get('title') or entry_url,
                })
            return {'type': 'playlist', 'entries': result}

        title = info.get('title') or url
        actual_url = info.get('webpage_url') or url
        return {'type': 'single', 'url': actual_url, 'title': title}

    def fetch_formats(self, url, cookies_path=None):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'js_runtimes': {'deno': {'path': self._deno_path}},
            'ffmpeg_location': self._ffmpeg_path,
            'remote_components': ['ejs:github'],
            'cookies': cookies_path,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        raw = sorted(
            info.get('formats', []),
            key=lambda f: (f.get('height') or 0, f.get('tbr') or 0),
            reverse=True,
        )

        video_formats: list[tuple[str, str, bool]] = []
        audio_formats: list[tuple[str, str]] = []
        for f in raw:
            fid = f.get('format_id', '?')
            ext = f.get('ext', '?')
            vcodec = f.get('vcodec') or 'none'
            acodec = f.get('acodec') or 'none'
            has_video = vcodec != 'none'
            has_audio = acodec != 'none'

            if has_video:
                height = f.get('height')
                res = f"{height}p" if height else "?"
                tbr = f.get('tbr') or f.get('vbr')
                brate = f" – {tbr:.0f}kbps" if tbr else ""
                marker = " ★" if has_audio else ""
                label = f"{res} {vcodec} ({ext}) [{fid}]{brate}{marker}"
                video_formats.append((label, fid, has_audio))
            elif has_audio:
                abr = f.get('abr') or f.get('tbr')
                brate = f" – {abr:.0f}kbps" if abr else ""
                label = f"{acodec} ({ext}) [{fid}]{brate}"
                audio_formats.append((label, fid))

        # Subtitle extraction
        subtitles_raw = info.get('subtitles') or {}
        auto_captions_raw = info.get('automatic_captions') or {}
        primary_lang = (info.get('language') or '').lower()
        manual_langs = frozenset(subtitles_raw.keys())

        subtitle_list: list[tuple[str, str, bool]] = []

        for lang, formats in sorted(subtitles_raw.items()):
            if not formats:
                continue
            exts = ', '.join(dict.fromkeys(
                f['ext'] for f in formats if f.get('ext') in _DISPLAY_SUB_EXTS
            )) or 'best'
            name = next((f.get('name') for f in formats if f.get('name')), lang)
            subtitle_list.append((f"{lang} – {name} [{exts}]", lang, False))

        for lang, formats in sorted(auto_captions_raw.items()):
            if not formats or lang in _SKIP_AUTO_LANGS:
                continue
            # When primary language is known, limit auto captions to that language family
            if primary_lang:
                lang_base = lang.split('-')[0].lower()
                if lang_base != primary_lang.split('-')[0] and lang not in manual_langs:
                    continue
            exts = ', '.join(dict.fromkeys(
                f['ext'] for f in formats if f.get('ext') in _DISPLAY_SUB_EXTS
            )) or 'best'
            name = next((f.get('name') for f in formats if f.get('name')), lang)
            label = f"{lang} – {name} {t('orig_sub_auto_marker')} [{exts}]"
            subtitle_list.append((label, lang, True))

        return {
            "title": info.get('title', ''),
            "video": video_formats,
            "audio": audio_formats,
            "subtitles": subtitle_list,
        }

    def download_video(self, url, format_id, cookies_path=None, format_spec=None,
                       subtitle_opts=None, mp3_bitrate_override=None):
        if format_spec is not None:
            spec = format_spec
            _, is_audio = FORMAT_SPECS.get(format_id, ("best/best", False))
        elif format_id == "fmt_720p":
            spec = f"bestvideo[height<={self.video_resolution}][ext=mp4]+bestaudio[ext=m4a]/best"
            is_audio = False
        else:
            spec, is_audio = FORMAT_SPECS.get(format_id, ("best/best", False))

        ydl_opts = {
            'format': spec,
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [self._progress_hook],
            'js_runtimes': {'deno': {'path': self._deno_path}},
            'ffmpeg_location': self._ffmpeg_path,
            'remote_components': ['ejs:github'],
            'cookies': cookies_path,
        }

        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': mp3_bitrate_override or self.mp3_bitrate,
            }]
        else:
            ydl_opts['merge_output_format'] = 'mp4'

        if subtitle_opts:
            embed = subtitle_opts.get('embed', False)
            for key in ('writesubtitles', 'writeautomaticsub', 'subtitleslangs', 'subtitlesformat'):
                if key in subtitle_opts:
                    ydl_opts[key] = subtitle_opts[key]
            if embed:
                ydl_opts.setdefault('postprocessors', []).append(
                    {'key': 'FFmpegEmbedSubtitle', 'already_have_subtitle': False}
                )

        self.status_callback(t("dl_fetching"), 0)
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
