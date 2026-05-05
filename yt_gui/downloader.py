import os
import sys
from yt_dlp import YoutubeDL

from .formats import FORMAT_SPECS
from .i18n import t
from . import get_resource_base


class Downloader:
    def __init__(self, output_dir="downloads", status_callback=None):
        self.output_dir = output_dir
        self.status_callback = status_callback

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

    def download_video(self, url, format_id, cookies_path=None):
        format_spec, is_audio = FORMAT_SPECS.get(format_id, ("best/best", False))

        ydl_opts = {
            'format': format_spec,
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
                'preferredquality': '192',
            }]
        else:
            ydl_opts['merge_output_format'] = 'mp4'

        self.status_callback(t("dl_fetching"), 0)
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
