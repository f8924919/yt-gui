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

_ORIGINAL_KEY = "fmt_original"
_WIN_H_DEFAULT = 200
_WIN_H_EXPANDED = 370
_SUBTITLE_FORMATS = ("srt", "vtt", "best")


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()
        i18n.set_language(self._settings.language)

        self.title(t("app_title"))
        self.geometry(f"500x{_WIN_H_DEFAULT}")

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
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_changed)

        # Row 2: original format detail panel (hidden initially)
        self._original_frame = ttk.LabelFrame(main_frame, text=t("label_original_detail"), padding="5")
        self._create_original_format_widgets()

        self.download_button = ttk.Button(
            main_frame, text=t("btn_download"), command=self._start_download_thread,
        )
        self.download_button.grid(row=3, column=0, columnspan=2, pady=10)

        self.status_label = ttk.Label(
            main_frame, text=t("status_ready"), relief="sunken", anchor="w",
        )
        self.status_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)

        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=5, column=0, columnspan=2, sticky="ew")

        main_frame.grid_columnconfigure(1, weight=1)

    def _create_original_format_widgets(self):
        f = self._original_frame
        self._orig_video_formats: list[tuple[str, str, bool]] = []
        self._orig_audio_formats: list[tuple[str, str]] = []
        self._orig_subtitle_formats: list[tuple[str, str, bool]] = []

        # --- Row 0: Video (combo spans cols 1-2, fetch button at col 3) ---
        ttk.Label(f, text=t("label_orig_video")).grid(row=0, column=0, sticky="w", pady=3)
        self._orig_video_var = tk.StringVar(value=t("orig_auto"))
        self._orig_video_combo = ttk.Combobox(
            f, textvariable=self._orig_video_var, state="disabled", width=30,
        )
        self._orig_video_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=3, sticky="ew")
        self._orig_video_combo.bind("<<ComboboxSelected>>", self._on_video_format_changed)

        self._fetch_button = ttk.Button(
            f, text=t("btn_fetch_formats"), command=self._start_fetch_formats_thread,
        )
        self._fetch_button.grid(row=0, column=3, padx=5, pady=3)

        # --- Row 1: Audio (combo spans cols 1-2) ---
        ttk.Label(f, text=t("label_orig_audio")).grid(row=1, column=0, sticky="w", pady=3)
        self._orig_audio_var = tk.StringVar(value=t("orig_auto"))
        self._orig_audio_combo = ttk.Combobox(
            f, textvariable=self._orig_audio_var, state="disabled", width=30,
        )
        self._orig_audio_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=3, sticky="ew")

        # --- Row 2: Subtitle (combo at col 1, format combo at col 2, embed check at col 3) ---
        ttk.Label(f, text=t("label_orig_subtitle")).grid(row=2, column=0, sticky="w", pady=3)
        self._orig_subtitle_var = tk.StringVar(value=t("orig_sub_none"))
        self._orig_subtitle_combo = ttk.Combobox(
            f, textvariable=self._orig_subtitle_var, state="disabled", width=22,
        )
        self._orig_subtitle_combo.grid(row=2, column=1, padx=5, pady=3, sticky="ew")
        self._orig_subtitle_combo.bind("<<ComboboxSelected>>", self._on_subtitle_changed)

        self._orig_subtitle_fmt_var = tk.StringVar(value="srt")
        self._orig_subtitle_fmt_combo = ttk.Combobox(
            f, textvariable=self._orig_subtitle_fmt_var,
            values=_SUBTITLE_FORMATS, state=tk.DISABLED, width=5,
        )
        self._orig_subtitle_fmt_combo.grid(row=2, column=2, padx=(0, 5), pady=3)

        self._orig_embed_var = tk.BooleanVar(value=False)
        self._orig_embed_check = ttk.Checkbutton(
            f, text=t("orig_sub_embed"), variable=self._orig_embed_var, state=tk.DISABLED,
        )
        self._orig_embed_check.grid(row=2, column=3, padx=5, pady=3, sticky="w")

        f.grid_columnconfigure(1, weight=1)

    # ------------------------------------------------------------------ events

    def _on_format_changed(self, event=None):
        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]
        if format_id == _ORIGINAL_KEY:
            self._original_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
            self.geometry(f"500x{_WIN_H_EXPANDED}")
        else:
            self._original_frame.grid_remove()
            self.geometry(f"500x{_WIN_H_DEFAULT}")

    def _on_video_format_changed(self, event=None):
        auto_label = t("orig_auto")
        selected = self._orig_video_var.get()

        if selected == auto_label or not self._orig_video_formats:
            if self._orig_audio_var.get() == t("orig_audio_included"):
                self._orig_audio_var.set(auto_label)
            if self._orig_audio_formats:
                self._orig_audio_combo.config(state="readonly")
            return

        values = list(self._orig_video_combo["values"])
        try:
            idx = values.index(selected) - 1  # offset for leading auto entry
        except ValueError:
            return

        if 0 <= idx < len(self._orig_video_formats):
            _, _, is_combined = self._orig_video_formats[idx]
            if is_combined:
                self._orig_audio_var.set(t("orig_audio_included"))
                self._orig_audio_combo.config(state=tk.DISABLED)
            else:
                if self._orig_audio_var.get() == t("orig_audio_included"):
                    self._orig_audio_var.set(auto_label)
                self._orig_audio_combo.config(state="readonly")

    def _on_subtitle_changed(self, event=None):
        none_label = t("orig_sub_none")
        unavail_label = t("orig_sub_unavailable")
        selected = self._orig_subtitle_var.get()
        has_sub = selected not in (none_label, unavail_label) and bool(self._orig_subtitle_formats)
        state = "readonly" if has_sub else tk.DISABLED
        self._orig_subtitle_fmt_combo.config(state=state)
        self._orig_embed_check.config(state=tk.NORMAL if has_sub else tk.DISABLED)
        if not has_sub:
            self._orig_embed_var.set(False)

    # --------------------------------------------------------- format fetching

    def _start_fetch_formats_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(t("warn_title"), t("warn_no_url"))
            return

        cookies_path = self._settings.cookies_path or None
        if cookies_path and not os.path.isfile(cookies_path):
            cookies_path = None

        self._fetch_button.config(state=tk.DISABLED, text=t("btn_fetching"))
        self._orig_video_combo.config(state=tk.DISABLED)
        self._orig_audio_combo.config(state=tk.DISABLED)
        self._orig_subtitle_combo.config(state=tk.DISABLED)
        self._orig_subtitle_fmt_combo.config(state=tk.DISABLED)
        self._orig_embed_check.config(state=tk.DISABLED)
        self._update_status(t("status_fetching_formats"), 0)

        threading.Thread(
            target=self._run_fetch_formats, args=(url, cookies_path), daemon=True,
        ).start()

    def _run_fetch_formats(self, url, cookies_path):
        try:
            result = self.downloader.fetch_formats(url, cookies_path)
            self.after(0, self._populate_format_combos, result)
        except Exception as e:
            self.after(0, self._update_status, f"❌ {e}", 0)
            self.after(0, lambda err=e: messagebox.showerror(
                t("err_title"), t("err_fetch_formats").format(error=err),
            ))
        finally:
            self.after(0, lambda: self._fetch_button.config(
                state=tk.NORMAL, text=t("btn_fetch_formats"),
            ))

    def _populate_format_combos(self, result):
        auto_label = t("orig_auto")

        self._orig_video_formats = result["video"]
        self._orig_audio_formats = result["audio"]
        self._orig_subtitle_formats = result["subtitles"]

        video_labels = [auto_label] + [lbl for lbl, _, _ in self._orig_video_formats]
        audio_labels = [auto_label] + [lbl for lbl, _ in self._orig_audio_formats]

        self._orig_video_combo.config(values=video_labels, state="readonly")
        self._orig_video_var.set(auto_label)
        self._orig_audio_combo.config(values=audio_labels, state="readonly")
        self._orig_audio_var.set(auto_label)

        none_label = t("orig_sub_none")
        if self._orig_subtitle_formats:
            sub_labels = [none_label] + [lbl for lbl, _, _ in self._orig_subtitle_formats]
            self._orig_subtitle_combo.config(values=sub_labels, state="readonly")
            self._orig_subtitle_var.set(none_label)
        else:
            unavail = t("orig_sub_unavailable")
            self._orig_subtitle_combo.config(values=[unavail], state=tk.DISABLED)
            self._orig_subtitle_var.set(unavail)
        # fmt combo and embed check stay disabled until a subtitle is selected
        self._orig_subtitle_fmt_combo.config(state=tk.DISABLED)
        self._orig_embed_check.config(state=tk.DISABLED)

        self._update_status(
            t("status_formats_loaded").format(
                video=len(self._orig_video_formats),
                audio=len(self._orig_audio_formats),
                subtitle=len(self._orig_subtitle_formats),
            ),
            0,
        )

    def _build_original_format_spec(self) -> str:
        auto_label = t("orig_auto")
        video_sel = self._orig_video_var.get()
        audio_sel = self._orig_audio_var.get()

        video_id = None
        is_combined = False
        audio_id = None

        if video_sel != auto_label and self._orig_video_formats:
            values = list(self._orig_video_combo["values"])
            try:
                idx = values.index(video_sel) - 1
                if 0 <= idx < len(self._orig_video_formats):
                    _, video_id, is_combined = self._orig_video_formats[idx]
            except ValueError:
                pass

        if not is_combined and audio_sel not in (auto_label, t("orig_audio_included")):
            if self._orig_audio_formats:
                values = list(self._orig_audio_combo["values"])
                try:
                    idx = values.index(audio_sel) - 1
                    if 0 <= idx < len(self._orig_audio_formats):
                        _, audio_id = self._orig_audio_formats[idx]
                except ValueError:
                    pass

        if is_combined:
            return video_id
        if video_id and audio_id:
            return f"{video_id}+{audio_id}"
        if video_id:
            return f"{video_id}+bestaudio"
        if audio_id:
            return f"bestvideo+{audio_id}"
        return "bestvideo+bestaudio/best"

    def _build_original_subtitle_opts(self) -> dict | None:
        none_label = t("orig_sub_none")
        unavail_label = t("orig_sub_unavailable")
        selected = self._orig_subtitle_var.get()

        if selected in (none_label, unavail_label) or not self._orig_subtitle_formats:
            return None

        values = list(self._orig_subtitle_combo["values"])
        try:
            idx = values.index(selected) - 1
            if idx < 0 or idx >= len(self._orig_subtitle_formats):
                return None
            _, lang_code, is_auto = self._orig_subtitle_formats[idx]
        except ValueError:
            return None

        return {
            'writesubtitles': not is_auto,
            'writeautomaticsub': is_auto,
            'subtitleslangs': [lang_code],
            'subtitlesformat': self._orig_subtitle_fmt_var.get(),
            'embed': self._orig_embed_var.get(),
        }

    # ----------------------------------------------------------- settings/misc

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
            self._fetch_button.config(state=tk.DISABLED)
            self._orig_video_combo.config(state=tk.DISABLED)
            self._orig_audio_combo.config(state=tk.DISABLED)
            self._orig_subtitle_combo.config(state=tk.DISABLED)
            self._orig_subtitle_fmt_combo.config(state=tk.DISABLED)
            self._orig_embed_check.config(state=tk.DISABLED)
        else:
            self.download_button.config(state=tk.NORMAL, text=t("btn_download"))
            self.url_entry.config(state=tk.NORMAL)
            self.format_combo.config(state="readonly")
            self._fetch_button.config(state=tk.NORMAL)
            if self._orig_video_formats:
                self._orig_video_combo.config(state="readonly")
                self._on_video_format_changed()
            if self._orig_subtitle_formats:
                self._orig_subtitle_combo.config(state="readonly")
                self._on_subtitle_changed()

    # ------------------------------------------------------------ downloading

    def _start_download_thread(self):
        url = self.url_entry.get().strip()
        cookies_path = self._settings.cookies_path or None

        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]

        format_spec = None
        subtitle_opts = None
        if format_id == _ORIGINAL_KEY:
            format_spec = self._build_original_format_spec()
            subtitle_opts = self._build_original_subtitle_opts()

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
        threading.Thread(
            target=self._run_download, args=(url, format_id, cookies_path, format_spec, subtitle_opts),
        ).start()

    def _run_download(self, url, format_id, cookies_path=None, format_spec=None, subtitle_opts=None):
        try:
            self.downloader.download_video(url, format_id, cookies_path, format_spec, subtitle_opts)
        except Exception as e:
            self._update_status(f"❌ {e}", 0)
            self.after(0, lambda err=e: messagebox.showerror(
                t("err_title"),
                t("err_download").format(error=err),
            ))
        finally:
            self.after(100, self._set_downloading, False)
