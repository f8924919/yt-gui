import tkinter as tk
from tkinter import ttk, filedialog

from .settings import Settings, SettingsManager


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, manager: SettingsManager):
        super().__init__(parent)
        self.title("設定")
        self.resizable(False, False)
        self.grab_set()  # モーダル

        self._manager = manager
        self._settings = manager.load()

        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # ── 一般タブ ──────────────────────────────
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="一般")
        self._build_general_tab(general_frame)

        # ── ボタン行 ──────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text="保存", command=self._save).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="キャンセル", command=self.destroy).pack(side="right")

    def _build_general_tab(self, parent: ttk.Frame):
        ttk.Label(parent, text="保存フォルダ:").grid(row=0, column=0, sticky="w", pady=5)

        self._download_var = tk.StringVar(value=self._settings.download_path)
        ttk.Entry(parent, textvariable=self._download_var, width=45).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(parent, text="参照...", command=self._browse_download).grid(row=0, column=2, pady=5)

        ttk.Label(parent, text="Cookiesファイル:").grid(row=1, column=0, sticky="w", pady=5)

        self._cookies_var = tk.StringVar(value=self._settings.cookies_path)
        ttk.Entry(parent, textvariable=self._cookies_var, width=45).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(parent, text="参照...", command=self._browse_cookies).grid(row=1, column=2, pady=5)

        parent.grid_columnconfigure(1, weight=1)

    def _browse_download(self):
        path = filedialog.askdirectory(title="保存フォルダを選択")
        if path:
            self._download_var.set(path)

    def _browse_cookies(self):
        path = filedialog.askopenfilename(
            title="Cookiesファイルを選択",
            filetypes=[("テキストファイル", "*.txt"), ("すべてのファイル", "*.*")],
        )
        if path:
            self._cookies_var.set(path)

    def _save(self):
        self._settings.download_path = self._download_var.get().strip()
        self._settings.cookies_path = self._cookies_var.get().strip()
        self._manager.save(self._settings)
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
