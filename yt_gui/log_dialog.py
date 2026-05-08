import tkinter as tk
from tkinter import ttk, scrolledtext

from .i18n import t


class LogDialog(tk.Toplevel):
    def __init__(self, parent, on_close=None):
        super().__init__(parent)
        self.title(t("log_dialog_title"))
        self.geometry("640x420")
        self.minsize(400, 200)
        self.resizable(True, True)
        self._on_close_cb = on_close

        self._text = scrolledtext.ScrolledText(
            self, state=tk.DISABLED, wrap=tk.WORD,
            font=("Courier New", 9), bg="#1e1e1e", fg="#d4d4d4",
        )
        self._text.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text=t("btn_clear_log"), command=self._clear).pack(side="left")
        ttk.Button(btn_frame, text=t("btn_close"), command=self._on_close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def load(self, entries: list[str]):
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        if entries:
            self._text.insert(tk.END, "\n".join(entries) + "\n")
        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)

    def append(self, text: str):
        at_bottom = self._text.yview()[1] >= 0.99
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, text + "\n")
        self._text.config(state=tk.DISABLED)
        if at_bottom:
            self._text.see(tk.END)

    def _clear(self):
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()
