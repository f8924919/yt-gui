import tkinter as tk
from tkinter import ttk, messagebox
from yt_dlp import YoutubeDL
import threading
import os
import sys
from os.path import expanduser

# キー: (yt-dlpフォーマット指定文字列, 音声のみかどうか)
FORMAT_OPTIONS: dict[str, tuple[str, bool]] = {
    "最高画質 (MP4に結合)": ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", False),
    "720p (MP4に結合)": ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best", False),
    "MP3 (音声のみ・192kbps)": ("bestaudio/best", True),
    "オリジナルの形式": ("best/best", False),
}


class Downloader:
    def __init__(self, output_dir="downloads", status_callback=None):
        self.output_dir = output_dir
        self.status_callback = status_callback

        _ext = '.exe' if sys.platform == 'win32' else ''
        base = os.path.dirname(__file__)
        self._deno_path = os.path.join(base, f'deno{_ext}')
        self._ffmpeg_path = os.path.join(base, 'ffmpeg', f'ffmpeg{_ext}')

        os.makedirs(self.output_dir, exist_ok=True)

    def _progress_hook(self, d):
        if self.status_callback is None:
            return

        status = d['status']
        if status == 'finished':
            filename = d.get('filename', 'Unknown File')
            self.status_callback(f"✅ 完了: {os.path.basename(filename)}", 100)
        elif status == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                percent = downloaded_bytes / total_bytes * 100
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                self.status_callback(
                    f"⬇️ ダウンロード中: {d.get('_percent_str', '0.0%')} | 速度: {speed} | 残り: {eta}",
                    percent
                )
            else:
                self.status_callback(f"処理中... {d.get('_percent_str', '')}", 0)
        elif status == 'error':
            self.status_callback("❌ エラーが発生しました", 0)
        else:
            self.status_callback(f"状態: {status}...", 0)

    def download_video(self, url, format_key, cookies_path=None):
        format_spec, is_audio = FORMAT_OPTIONS.get(format_key, ("best/best", False))

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

        self.status_callback("🔍 情報取得中...", 0)
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI ダウンローダー")
        self.geometry("500x250")

        self._create_widgets()

        download_path = os.path.join(expanduser("~"), "Downloads")
        self.downloader = Downloader(download_path, status_callback=self._update_status)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="動画URL:").grid(row=0, column=0, sticky='w', pady=5)
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(main_frame, text="Cookies:").grid(row=1, column=0, sticky='w', pady=5)
        self.cookies_entry = ttk.Entry(main_frame, width=50)
        self.cookies_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        self.cookies_entry.insert(0, os.path.join(os.path.dirname(__file__), 'cookies.txt'))

        ttk.Label(main_frame, text="形式選択:").grid(row=2, column=0, sticky='w', pady=5)
        self.format_var = tk.StringVar(self)
        format_keys = list(FORMAT_OPTIONS.keys())
        self.format_var.set(format_keys[0])
        self.format_combo = ttk.Combobox(main_frame, textvariable=self.format_var, values=format_keys, state="readonly", width=48)
        self.format_combo.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        self.download_button = ttk.Button(main_frame, text="ダウンロード開始", command=self._start_download_thread)
        self.download_button.grid(row=3, column=0, columnspan=2, pady=10)

        self.status_label = ttk.Label(main_frame, text="URLと形式を選択してください", relief='sunken', anchor='w')
        self.status_label.grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=5, column=0, columnspan=2, sticky='ew')

        main_frame.grid_columnconfigure(1, weight=1)

    def _update_status(self, text, percent):
        self.status_label.config(text=text)
        self.progress_bar['value'] = percent

    def _set_downloading(self, downloading: bool):
        if downloading:
            self.download_button.config(state=tk.DISABLED, text="ダウンロード中...")
            self.url_entry.config(state=tk.DISABLED)
            self.format_combo.config(state=tk.DISABLED)
        else:
            self.download_button.config(state=tk.NORMAL, text="ダウンロード開始")
            self.url_entry.config(state=tk.NORMAL)
            self.format_combo.config(state="readonly")

    def _start_download_thread(self):
        url = self.url_entry.get().strip()
        format_key = self.format_var.get()
        cookies_path = self.cookies_entry.get().strip() or None

        if not url:
            messagebox.showwarning("警告", "ダウンロードするURLを入力してください。")
            return

        self._set_downloading(True)
        self._update_status("ダウンロード準備中...", 0)
        threading.Thread(target=self._run_download, args=(url, format_key, cookies_path)).start()

    def _run_download(self, url, format_key, cookies_path=None):
        try:
            self.downloader.download_video(url, format_key, cookies_path)
        except Exception as e:
            self._update_status(f"❌ 致命的なエラー: {str(e)}", 0)
            self.after(0, lambda: messagebox.showerror("エラー", f"ダウンロード中にエラーが発生しました:\n{e}"))
        finally:
            self.after(100, self._set_downloading, False)


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("致命的なエラー", f"アプリケーションの起動中にエラーが発生しました:\n{e}")
