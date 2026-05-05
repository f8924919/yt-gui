import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
from os.path import expanduser

from .formats import FORMAT_KEYS
from .downloader import Downloader
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from . import get_resource_base
from . import i18n
from .i18n import t


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()
        i18n.set_language(self._settings.language)

        self.title(t("app_title"))
        self.geometry("500x200")

        icon_path = os.path.join(get_resource_base(), "assets", "icon.png")
        if os.path.isfile(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, img)
            except Exception:
                pass

        if not self._settings.cookies_path:
            default = os.path.join(get_resource_base(), "cookies.txt")
            if os.path.isfile(default):
                self._settings.cookies_path = default

        self._create_menu()
        self._create_widgets()

        self.downloader = Downloader(self._resolve_download_path(), status_callback=self._update_status)

    def _resolve_download_path(self) -> str:
        path = self._settings.download_path
        return path if path else os.path.join(expanduser("~"), "Downloads")

    def _create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label=t("menu_settings"), accelerator="Ctrl+,", command=self._open_settings)
        self.bind_all("<Control-comma>", lambda _: self._open_settings())

        if sys.platform != "darwin":
            file_menu.add_separator()
            file_menu.add_command(label=t("menu_quit"), command=self.quit)

        menubar.add_cascade(label=t("menu_file"), menu=file_menu)
        self.config(menu=menubar)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=t("label_url")).grid(row=0, column=0, sticky="w", pady=5)
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(main_frame, text=t("label_format")).grid(row=1, column=0, sticky="w", pady=5)
        self._format_display = [t(k) for k in FORMAT_KEYS]
        self.format_var = tk.StringVar(self, value=self._format_display[0])
        self.format_combo = ttk.Combobox(
            main_frame, textvariable=self.format_var, values=self._format_display,
            state="readonly", width=48,
        )
        self.format_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.download_button = ttk.Button(
            main_frame, text=t("btn_download"), command=self._start_download_thread,
        )
        self.download_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.status_label = ttk.Label(
            main_frame, text=t("status_ready"), relief="sunken", anchor="w",
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky="ew")

        main_frame.grid_columnconfigure(1, weight=1)

    def _open_settings(self):
        dialog = SettingsDialog(self, self._settings_manager)
        self.wait_window(dialog)
        self._settings = self._settings_manager.load()
        self.downloader.output_dir = self._resolve_download_path()

    def _update_status(self, text, percent):
        self.status_label.config(text=text)
        self.progress_bar["value"] = percent

    def _set_downloading(self, downloading: bool):
        if downloading:
            self.download_button.config(state=tk.DISABLED, text=t("btn_downloading"))
            self.url_entry.config(state=tk.DISABLED)
            self.format_combo.config(state=tk.DISABLED)
        else:
            self.download_button.config(state=tk.NORMAL, text=t("btn_download"))
            self.url_entry.config(state=tk.NORMAL)
            self.format_combo.config(state="readonly")

    def _start_download_thread(self):
        url = self.url_entry.get().strip()
        cookies_path = self._settings.cookies_path or None

        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]

        if not url:
            messagebox.showwarning(t("warn_title"), t("warn_no_url"))
            return

        if cookies_path and not os.path.isfile(cookies_path):
            messagebox.showwarning(
                t("warn_title"),
                t("warn_cookies_not_found").format(path=cookies_path),
            )
            cookies_path = None

        self._set_downloading(True)
        self._update_status(t("status_preparing"), 0)
        threading.Thread(target=self._run_download, args=(url, format_id, cookies_path)).start()

    def _run_download(self, url, format_id, cookies_path=None):
        try:
            self.downloader.download_video(url, format_id, cookies_path)
        except Exception as e:
            self._update_status(f"❌ {e}", 0)
            self.after(0, lambda: messagebox.showerror(
                t("err_title"),
                t("err_download").format(error=e),
            ))
        finally:
            self.after(100, self._set_downloading, False)
