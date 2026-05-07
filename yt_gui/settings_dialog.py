import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .settings import Settings, SettingsManager
from .formats import VIDEO_RESOLUTIONS, MP3_BITRATES
from .i18n import t, AVAILABLE_LANGUAGES

# yt-dlp がサポートするブラウザ（表示名, 内部名）
_BROWSERS = [
    ("Brave", "brave"),
    ("Chrome", "chrome"),
    ("Chromium", "chromium"),
    ("Edge", "edge"),
    ("Firefox", "firefox"),
    ("Opera", "opera"),
    ("Vivaldi", "vivaldi"),
    ("Whale", "whale"),
]
if sys.platform == "darwin":
    _BROWSERS.append(("Safari", "safari"))

_BROWSER_DISPLAY = [label for label, _ in _BROWSERS]
_BROWSER_INTERNAL = [name for _, name in _BROWSERS]


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, manager: SettingsManager):
        super().__init__(parent)
        self.title(t("settings_title"))
        self.resizable(False, False)
        self.grab_set()

        self._manager = manager
        self._settings = manager.load()

        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text=t("tab_general"))
        self._build_general_tab(general_frame)

        quality_frame = ttk.Frame(notebook, padding=10)
        notebook.add(quality_frame, text=t("tab_quality"))
        self._build_quality_tab(quality_frame)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text=t("btn_save"), command=self._save).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text=t("btn_cancel"), command=self.destroy).pack(side="right")

    def _build_general_tab(self, parent: ttk.Frame):
        # Row 0: Download folder
        ttk.Label(parent, text=t("label_download_folder")).grid(row=0, column=0, sticky="w", pady=5)
        self._download_var = tk.StringVar(value=self._settings.download_path)
        ttk.Entry(parent, textvariable=self._download_var, width=45).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(parent, text=t("btn_browse"), command=self._browse_download).grid(row=0, column=2, pady=5)

        # Row 1: Cookies source radio buttons
        ttk.Label(parent, text=t("label_cookies_source")).grid(row=1, column=0, sticky="w", pady=5)

        if self._settings.cookies_browser:
            initial_source = "browser"
        elif self._settings.cookies_path:
            initial_source = "file"
        else:
            initial_source = "none"
        self._cookies_source_var = tk.StringVar(value=initial_source)

        radio_frame = ttk.Frame(parent)
        radio_frame.grid(row=1, column=1, columnspan=2, sticky="w", pady=5)
        for value, key in (("none", "cookies_source_none"), ("file", "cookies_source_file"), ("browser", "cookies_source_browser")):
            ttk.Radiobutton(
                radio_frame, text=t(key),
                variable=self._cookies_source_var, value=value,
                command=self._on_cookies_source_changed,
            ).pack(side="left", padx=(0, 10))

        # Row 2: File detail frame (shown when source=file)
        self._file_frame = ttk.Frame(parent)
        self._cookies_var = tk.StringVar(value=self._settings.cookies_path)
        ttk.Entry(self._file_frame, textvariable=self._cookies_var, width=40).pack(side="left", padx=(0, 5))
        ttk.Button(self._file_frame, text=t("btn_browse"), command=self._browse_cookies).pack(side="left")

        # Row 2: Browser detail frame (shown when source=browser)
        self._browser_frame = ttk.Frame(parent)
        current_browser_display = ""
        if self._settings.cookies_browser in _BROWSER_INTERNAL:
            current_browser_display = _BROWSER_DISPLAY[_BROWSER_INTERNAL.index(self._settings.cookies_browser)]
        self._browser_var = tk.StringVar(value=current_browser_display)
        ttk.Combobox(
            self._browser_frame, textvariable=self._browser_var,
            values=_BROWSER_DISPLAY, state="readonly", width=20,
        ).pack(side="left")

        # Row 3: Language
        ttk.Label(parent, text=t("label_language")).grid(row=3, column=0, sticky="w", pady=5)
        self._lang_display = [t(f"lang_{lang}") for lang in AVAILABLE_LANGUAGES]
        current_display = t(f"lang_{self._settings.language}")
        self._lang_var = tk.StringVar(value=current_display)
        ttk.Combobox(
            parent, textvariable=self._lang_var, values=self._lang_display,
            state="readonly", width=20,
        ).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        parent.grid_columnconfigure(1, weight=1)

        # Show the appropriate detail frame based on initial source
        self._on_cookies_source_changed()

    def _on_cookies_source_changed(self):
        self._file_frame.grid_remove()
        self._browser_frame.grid_remove()
        source = self._cookies_source_var.get()
        if source == "file":
            self._file_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 5))
        elif source == "browser":
            self._browser_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 5))

    def _build_quality_tab(self, parent: ttk.Frame):
        ttk.Label(parent, text=t("label_video_resolution")).grid(row=0, column=0, sticky="w", pady=5)
        res_values = [f"{r}p" for r in VIDEO_RESOLUTIONS]
        self._res_var = tk.StringVar(value=f"{self._settings.video_resolution}p")
        ttk.Combobox(
            parent, textvariable=self._res_var, values=res_values,
            state="readonly", width=10,
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(parent, text=t("label_mp3_bitrate")).grid(row=1, column=0, sticky="w", pady=5)
        bitrate_values = [f"{b}kbps" for b in MP3_BITRATES]
        self._bitrate_var = tk.StringVar(value=f"{self._settings.mp3_bitrate}kbps")
        ttk.Combobox(
            parent, textvariable=self._bitrate_var, values=bitrate_values,
            state="readonly", width=10,
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(parent, text=t("quality_note"), foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(10, 0),
        )

    def _browse_download(self):
        path = filedialog.askdirectory(title=t("dialog_select_folder"))
        if path:
            self._download_var.set(path)

    def _browse_cookies(self):
        path = filedialog.askopenfilename(
            title=t("label_cookies_file"),
            filetypes=[
                (t("filetype_text"), "*.txt"),
                (t("filetype_all"), "*.*"),
            ],
        )
        if path:
            self._cookies_var.set(path)

    def _save(self):
        old_lang = self._settings.language
        selected_idx = self._lang_display.index(self._lang_var.get())
        new_lang = AVAILABLE_LANGUAGES[selected_idx]

        self._settings.download_path = self._download_var.get().strip()
        self._settings.language = new_lang
        self._settings.video_resolution = self._res_var.get().removesuffix("p")
        self._settings.mp3_bitrate = self._bitrate_var.get().removesuffix("kbps")

        source = self._cookies_source_var.get()
        if source == "file":
            self._settings.cookies_path = self._cookies_var.get().strip()
            self._settings.cookies_browser = ""
        elif source == "browser":
            selected_display = self._browser_var.get()
            if selected_display in _BROWSER_DISPLAY:
                self._settings.cookies_browser = _BROWSER_INTERNAL[_BROWSER_DISPLAY.index(selected_display)]
            else:
                self._settings.cookies_browser = ""
            self._settings.cookies_path = ""
        else:
            self._settings.cookies_path = ""
            self._settings.cookies_browser = ""

        self._manager.save(self._settings)

        if new_lang != old_lang:
            messagebox.showinfo(t("settings_title"), t("restart_required"))

        self.destroy()

    def _center_on_parent(self, parent: tk.Tk):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.winfo_width()
        dh = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
