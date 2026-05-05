import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
from os.path import expanduser

from .formats import FORMAT_OPTIONS
from .downloader import Downloader
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from . import get_resource_base


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI ダウンローダー")
        self.geometry("500x200")

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()

        # デフォルトのcookiesパスを補完
        if not self._settings.cookies_path:
            default = os.path.join(get_resource_base(), "cookies.txt")
            if os.path.isfile(default):
                self._settings.cookies_path = default

        self._create_menu()
        self._create_widgets()

        download_path = os.path.join(expanduser("~"), "Downloads")
        self.downloader = Downloader(download_path, status_callback=self._update_status)

    def _create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="設定...", accelerator="Ctrl+,", command=self._open_settings)
        self.bind_all("<Control-comma>", lambda _: self._open_settings())

        # macOS はアプリメニューに Quit が自動追加されるため省略
        if sys.platform != "darwin":
            file_menu.add_separator()
            file_menu.add_command(label="終了", command=self.quit)

        menubar.add_cascade(label="ファイル", menu=file_menu)

        self.config(menu=menubar)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="動画URL:").grid(row=0, column=0, sticky="w", pady=5)
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(main_frame, text="形式選択:").grid(row=1, column=0, sticky="w", pady=5)
        self.format_var = tk.StringVar(self)
        format_keys = list(FORMAT_OPTIONS.keys())
        self.format_var.set(format_keys[0])
        self.format_combo = ttk.Combobox(
            main_frame, textvariable=self.format_var, values=format_keys,
            state="readonly", width=48,
        )
        self.format_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.download_button = ttk.Button(
            main_frame, text="ダウンロード開始", command=self._start_download_thread,
        )
        self.download_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.status_label = ttk.Label(
            main_frame, text="URLと形式を選択してください", relief="sunken", anchor="w",
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky="ew")

        main_frame.grid_columnconfigure(1, weight=1)

    def _open_settings(self):
        SettingsDialog(self, self._settings_manager)
        # ダイアログ閉幕後に最新設定を反映
        self._settings = self._settings_manager.load()

    def _update_status(self, text, percent):
        self.status_label.config(text=text)
        self.progress_bar["value"] = percent

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
        cookies_path = self._settings.cookies_path or None

        if not url:
            messagebox.showwarning("警告", "ダウンロードするURLを入力してください。")
            return

        if cookies_path and not os.path.isfile(cookies_path):
            messagebox.showwarning(
                "警告",
                f"Cookiesファイルが見つかりません:\n{cookies_path}\n\nCookiesなしでダウンロードを続行します。",
            )
            cookies_path = None

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
