import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .settings import Settings, SettingsManager
from .i18n import t, AVAILABLE_LANGUAGES


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

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text=t("btn_save"), command=self._save).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text=t("btn_cancel"), command=self.destroy).pack(side="right")

    def _build_general_tab(self, parent: ttk.Frame):
        ttk.Label(parent, text=t("label_download_folder")).grid(row=0, column=0, sticky="w", pady=5)

        self._download_var = tk.StringVar(value=self._settings.download_path)
        ttk.Entry(parent, textvariable=self._download_var, width=45).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(parent, text=t("btn_browse"), command=self._browse_download).grid(row=0, column=2, pady=5)

        ttk.Label(parent, text=t("label_cookies")).grid(row=1, column=0, sticky="w", pady=5)

        self._cookies_var = tk.StringVar(value=self._settings.cookies_path)
        ttk.Entry(parent, textvariable=self._cookies_var, width=45).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(parent, text=t("btn_browse"), command=self._browse_cookies).grid(row=1, column=2, pady=5)

        ttk.Label(parent, text=t("label_language")).grid(row=2, column=0, sticky="w", pady=5)

        self._lang_display = [t(f"lang_{lang}") for lang in AVAILABLE_LANGUAGES]
        current_display = t(f"lang_{self._settings.language}")
        self._lang_var = tk.StringVar(value=current_display)
        ttk.Combobox(
            parent, textvariable=self._lang_var, values=self._lang_display,
            state="readonly", width=20,
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        parent.grid_columnconfigure(1, weight=1)

    def _browse_download(self):
        path = filedialog.askdirectory(title=t("dialog_select_folder"))
        if path:
            self._download_var.set(path)

    def _browse_cookies(self):
        path = filedialog.askopenfilename(
            title=t("label_cookies"),
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
        self._settings.cookies_path = self._cookies_var.get().strip()
        self._settings.language = new_lang
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
