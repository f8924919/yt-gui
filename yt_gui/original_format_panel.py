import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from .downloader import Downloader
from .i18n import t
from .utils import strip_ansi

_SUBTITLE_FORMATS = ("srt", "vtt", "best")


class OriginalFormatPanel(ttk.LabelFrame):
    """オリジナル形式の詳細設定パネル。

    フォーマット取得・選択・字幕設定の状態とロジックをすべて内包する。
    App 側は get_format_spec() / get_subtitle_opts() / get_remux_only() 等の
    公開メソッドで結果を受け取るだけでよい。
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        downloader: Downloader,
        get_url: Callable[[], str],
        get_cookies: Callable[[], tuple[str | None, str | None]],
        update_status: Callable[[str, float], None],
    ):
        super().__init__(parent, text=t("label_original_detail"), padding="5")
        self._downloader = downloader
        self._get_url = get_url
        self._get_cookies = get_cookies
        self._update_status = update_status

        self._video_formats: list[tuple[str, str, bool]] = []
        self._audio_formats: list[tuple[str, str]] = []
        self._subtitle_formats: list[tuple[str, str, bool]] = []
        self._fetched_title: str = ""

        self._build_widgets()

    # ── widget construction ──────────────────────────────────────────────────

    def _build_widgets(self):
        # Row 0: Video combo + fetch button
        ttk.Label(self, text=t("label_orig_video")).grid(row=0, column=0, sticky="w", pady=3)
        self._video_var = tk.StringVar(value=t("orig_auto"))
        self._video_combo = ttk.Combobox(
            self, textvariable=self._video_var, state="disabled", width=30,
        )
        self._video_combo.grid(row=0, column=1, columnspan=2, padx=5, pady=3, sticky="ew")
        self._video_combo.bind("<<ComboboxSelected>>", self._on_video_changed)

        self._fetch_button = ttk.Button(
            self, text=t("btn_fetch_formats"), command=self._start_fetch_thread,
        )
        self._fetch_button.grid(row=0, column=3, padx=5, pady=3)

        # Row 1: Audio combo
        ttk.Label(self, text=t("label_orig_audio")).grid(row=1, column=0, sticky="w", pady=3)
        self._audio_var = tk.StringVar(value=t("orig_auto"))
        self._audio_combo = ttk.Combobox(
            self, textvariable=self._audio_var, state="disabled", width=30,
        )
        self._audio_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=3, sticky="ew")

        # Row 2: Subtitle listbox + format/embed controls
        ttk.Label(self, text=t("label_orig_subtitle")).grid(row=2, column=0, sticky="nw", pady=3)

        sub_list_frame = ttk.Frame(self)
        sub_list_frame.grid(row=2, column=1, columnspan=2, padx=5, pady=3, sticky="ew")
        self._subtitle_listbox = tk.Listbox(
            sub_list_frame, selectmode=tk.MULTIPLE, height=3, exportselection=False,
            state=tk.DISABLED,
        )
        sub_vsb = ttk.Scrollbar(sub_list_frame, orient="vertical",
                                command=self._subtitle_listbox.yview)
        self._subtitle_listbox.configure(yscrollcommand=sub_vsb.set)
        self._subtitle_listbox.pack(side="left", fill="both", expand=True)
        sub_vsb.pack(side="right", fill="y")
        self._subtitle_listbox.bind("<<ListboxSelect>>", self._on_subtitle_changed)

        sub_right_frame = ttk.Frame(self)
        sub_right_frame.grid(row=2, column=3, padx=5, pady=3, sticky="nw")
        self._subtitle_fmt_var = tk.StringVar(value="srt")
        self._subtitle_fmt_combo = ttk.Combobox(
            sub_right_frame, textvariable=self._subtitle_fmt_var,
            values=_SUBTITLE_FORMATS, state=tk.DISABLED, width=5,
        )
        self._subtitle_fmt_combo.pack(anchor="w")
        self._embed_var = tk.BooleanVar(value=False)
        self._embed_check = ttk.Checkbutton(
            sub_right_frame, text=t("orig_sub_embed"), variable=self._embed_var,
            state=tk.DISABLED,
        )
        self._embed_check.pack(anchor="w", pady=(4, 0))

        # Row 3: Output format radio buttons
        ttk.Label(self, text=t("label_orig_output")).grid(row=3, column=0, sticky="w", pady=3)
        self._remux_var = tk.BooleanVar(value=False)
        out_frame = ttk.Frame(self)
        out_frame.grid(row=3, column=1, columnspan=3, padx=5, pady=3, sticky="w")
        ttk.Radiobutton(
            out_frame, text=t("orig_output_mp4"), variable=self._remux_var, value=False,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            out_frame, text=t("orig_output_remux"), variable=self._remux_var, value=True,
        ).pack(side="left")

        self.grid_columnconfigure(1, weight=1)

    # ── public interface ─────────────────────────────────────────────────────

    def has_formats_loaded(self) -> bool:
        return self._video_combo["state"] == "readonly" and bool(self._fetched_title)

    def get_fetched_title(self) -> str:
        return self._fetched_title

    def is_both_skipped(self) -> bool:
        skip = t("orig_skip")
        return self._video_var.get() == skip and self._audio_var.get() == skip

    def get_remux_only(self) -> bool:
        return bool(self._remux_var.get())

    def get_format_spec(self) -> str:
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")
        video_sel = self._video_var.get()
        audio_sel = self._audio_var.get()

        video_skip = video_sel == skip_label
        audio_skip = audio_sel == skip_label

        video_id = None
        is_combined = False
        audio_id = None

        if video_sel not in (auto_label, skip_label) and self._video_formats:
            idx = self._format_index(self._video_combo, video_sel)
            if idx is not None and 0 <= idx < len(self._video_formats):
                _, video_id, is_combined = self._video_formats[idx]

        if not is_combined and audio_sel not in (auto_label, skip_label, t("orig_audio_included")):
            if self._audio_formats:
                idx = self._format_index(self._audio_combo, audio_sel)
                if idx is not None and 0 <= idx < len(self._audio_formats):
                    _, audio_id = self._audio_formats[idx]

        if is_combined:
            return video_id
        if video_skip:
            return audio_id if audio_id else "bestaudio/best"
        if audio_skip:
            return video_id if video_id else "bestvideo/best"
        if video_id and audio_id:
            return f"{video_id}+{audio_id}"
        if video_id:
            return f"{video_id}+bestaudio"
        if audio_id:
            return f"bestvideo+{audio_id}"
        return "bestvideo+bestaudio/best"

    def get_subtitle_opts(self) -> dict | None:
        sel = self._subtitle_listbox.curselection()
        if not sel or not self._subtitle_formats:
            return None

        lang_codes: list[str] = []
        has_manual = False
        has_auto = False
        for idx in sel:
            if 0 <= idx < len(self._subtitle_formats):
                _, lang_code, is_auto = self._subtitle_formats[idx]
                lang_codes.append(lang_code)
                if is_auto:
                    has_auto = True
                else:
                    has_manual = True

        if not lang_codes:
            return None

        return {
            'writesubtitles': has_manual,
            'writeautomaticsub': has_auto,
            'subtitleslangs': lang_codes,
            'subtitlesformat': self._subtitle_fmt_var.get(),
            'embed': self._embed_var.get(),
        }

    # ── internal events ──────────────────────────────────────────────────────

    def _on_video_changed(self, event=None):
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")
        selected = self._video_var.get()

        if selected in (auto_label, skip_label) or not self._video_formats:
            if self._audio_var.get() == t("orig_audio_included"):
                self._audio_var.set(auto_label)
            if self._audio_formats:
                self._audio_combo.config(state="readonly")
            return

        idx = self._format_index(self._video_combo, selected)
        if idx is None:
            return

        if 0 <= idx < len(self._video_formats):
            _, _, is_combined = self._video_formats[idx]
            if is_combined:
                self._audio_var.set(t("orig_audio_included"))
                self._audio_combo.config(state=tk.DISABLED)
            else:
                if self._audio_var.get() == t("orig_audio_included"):
                    self._audio_var.set(auto_label)
                self._audio_combo.config(state="readonly")

    def _on_subtitle_changed(self, event=None):
        sel = self._subtitle_listbox.curselection()
        has_sub = bool(sel) and bool(self._subtitle_formats)
        state = "readonly" if has_sub else tk.DISABLED
        self._subtitle_fmt_combo.config(state=state)
        self._embed_check.config(state=tk.NORMAL if has_sub else tk.DISABLED)
        if not has_sub:
            self._embed_var.set(False)

    @staticmethod
    def _format_index(combo, selected: str) -> int | None:
        """「自動」「スキップ」2件分のオフセットを除いたインデックスを返す。"""
        try:
            return list(combo["values"]).index(selected) - 2
        except ValueError:
            return None

    # ── format fetching ──────────────────────────────────────────────────────

    def _start_fetch_thread(self):
        url = self._get_url()
        if not url:
            messagebox.showwarning(t("warn_title"), t("warn_no_url"))
            return

        cookies_path, cookies_browser = self._get_cookies()

        self._fetch_button.config(state=tk.DISABLED, text=t("btn_fetching"))
        self._video_combo.config(state=tk.DISABLED)
        self._audio_combo.config(state=tk.DISABLED)
        self._subtitle_listbox.config(state=tk.DISABLED)
        self._subtitle_fmt_combo.config(state=tk.DISABLED)
        self._embed_check.config(state=tk.DISABLED)
        self._update_status(t("status_fetching_formats"), 0)

        threading.Thread(
            target=self._run_fetch, args=(url, cookies_path, cookies_browser), daemon=True,
        ).start()

    def _run_fetch(self, url, cookies_path, cookies_browser):
        try:
            result = self._downloader.fetch_formats(url, cookies_path, cookies_browser)
            self.after(0, self._on_fetch_done, result)
        except Exception as e:
            self.after(0, self._update_status, f"❌ {strip_ansi(str(e))}", 0)
            self.after(0, lambda err=e: messagebox.showerror(
                t("err_title"), t("err_fetch_formats").format(error=strip_ansi(str(err))),
            ))
        finally:
            self.after(0, lambda: self._fetch_button.config(
                state=tk.NORMAL, text=t("btn_fetch_formats"),
            ))

    def _on_fetch_done(self, result):
        auto_label = t("orig_auto")
        skip_label = t("orig_skip")

        self._fetched_title = result.get("title", "")
        self._video_formats = result["video"]
        self._audio_formats = result["audio"]
        self._subtitle_formats = result["subtitles"]

        video_labels = [auto_label, skip_label] + [lbl for lbl, _, _ in self._video_formats]
        audio_labels = [auto_label, skip_label] + [lbl for lbl, _ in self._audio_formats]

        self._video_combo.config(values=video_labels, state="readonly")
        self._video_var.set(auto_label)
        self._audio_combo.config(values=audio_labels, state="readonly")
        self._audio_var.set(auto_label)

        self._subtitle_listbox.config(state=tk.NORMAL)
        self._subtitle_listbox.delete(0, tk.END)
        if self._subtitle_formats:
            for lbl, _, _ in self._subtitle_formats:
                self._subtitle_listbox.insert(tk.END, lbl)
        else:
            self._subtitle_listbox.insert(tk.END, t("orig_sub_unavailable"))
            self._subtitle_listbox.config(state=tk.DISABLED)
        self._subtitle_fmt_combo.config(state=tk.DISABLED)
        self._embed_check.config(state=tk.DISABLED)

        self._update_status(
            t("status_formats_loaded").format(
                video=len(self._video_formats),
                audio=len(self._audio_formats),
                subtitle=len(self._subtitle_formats),
            ),
            0,
        )
