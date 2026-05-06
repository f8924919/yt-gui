import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
from os.path import expanduser
from dataclasses import dataclass

from .formats import FORMAT_KEYS
from .downloader import Downloader
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from . import get_resource_base
from . import i18n
from .i18n import t

_ORIGINAL_KEY = "fmt_original"
_WIN_H_DEFAULT = 480
_WIN_H_EXPANDED = 700
_SUBTITLE_FORMATS = ("srt", "vtt", "best")


@dataclass
class _QueueItem:
    url: str
    format_id: str
    format_label: str
    format_spec: str | None
    subtitle_opts: dict | None
    title: str = ""
    mp3_bitrate: str | None = None  # snapshotted at add time for fmt_mp3
    status: str = "waiting"  # waiting | downloading | done | error
    tree_iid: str = ""


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self._settings_manager = SettingsManager()
        self._settings = self._settings_manager.load()
        i18n.set_language(self._settings.language)

        self.title(t("app_title"))
        self.geometry(f"520x{_WIN_H_DEFAULT}")
        self.minsize(520, 380)
        self.resizable(True, True)

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

        self._queue_items: list[_QueueItem] = []
        self._queue_lock = threading.Lock()
        self._worker_running = False
        self._paused = False
        self._showing_pause_button = False
        self._item_counter = 0
        self._fetched_title: str = ""

        self._create_menu()
        self._create_widgets()

        self.downloader = Downloader(
            self._resolve_download_path(),
            status_callback=self._update_status,
            video_resolution=self._settings.video_resolution,
            mp3_bitrate=self._settings.mp3_bitrate,
        )

    def _resolve_download_path(self) -> str:
        path = self._settings.download_path
        return path if path else os.path.join(expanduser("~"), "Downloads")

    def _build_format_display(self) -> list[str]:
        result = []
        for k in FORMAT_KEYS:
            if k == "fmt_720p":
                result.append(t("fmt_720p").format(resolution=self._settings.video_resolution))
            elif k == "fmt_mp3":
                result.append(t("fmt_mp3").format(bitrate=self._settings.mp3_bitrate))
            else:
                result.append(t(k))
        return result

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
        self._format_display = self._build_format_display()
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

        # Row 3: Action buttons
        _action_frame = ttk.Frame(main_frame)
        _action_frame.grid(row=3, column=0, columnspan=2, pady=(10, 5))
        self.add_button = ttk.Button(
            _action_frame, text=t("btn_add"), command=self._add_url,
        )
        self.add_button.pack(side="left")

        # Row 4: Queue panel (expands vertically)
        queue_frame = ttk.LabelFrame(main_frame, text=t("queue_title"), padding="5")
        queue_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=5)

        cols = ("no", "url", "format", "status")
        self._queue_tree = ttk.Treeview(queue_frame, columns=cols, show="headings", height=5)
        self._queue_tree.heading("no", text="#")
        self._queue_tree.heading("url", text=t("queue_col_title"))
        self._queue_tree.heading("format", text=t("queue_col_format"))
        self._queue_tree.heading("status", text=t("queue_col_status"))
        self._queue_tree.column("no", width=32, minwidth=32, stretch=False)
        self._queue_tree.column("url", width=230, stretch=True)
        self._queue_tree.column("format", width=130, minwidth=100, stretch=False)
        self._queue_tree.column("status", width=110, minwidth=80, stretch=False)

        self._queue_tree.tag_configure("downloading", foreground="#1565c0")
        self._queue_tree.tag_configure("done", foreground="#2e7d32")
        self._queue_tree.tag_configure("error", foreground="#c62828")

        vsb = ttk.Scrollbar(queue_frame, orient="vertical", command=self._queue_tree.yview)
        self._queue_tree.configure(yscrollcommand=vsb.set)
        self._queue_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        queue_frame.grid_columnconfigure(0, weight=1)
        queue_frame.grid_rowconfigure(0, weight=1)

        btn_frame = ttk.Frame(queue_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        self.start_queue_button = ttk.Button(
            btn_frame, text=t("btn_start_queue"), command=self._start_queue,
        )
        self.start_queue_button.pack(side="left", padx=(0, 5))
        self.pause_queue_button = ttk.Button(
            btn_frame, text=t("btn_pause_queue"), command=self._pause_queue,
        )
        # pause button is not packed initially; shown only while worker is running
        self.remove_item_button = ttk.Button(
            btn_frame, text=t("btn_remove_item"), command=self._remove_selected,
        )
        self.remove_item_button.pack(side="left")

        # Row 5: Status label
        self.status_label = ttk.Label(
            main_frame, text=t("status_ready"), relief="sunken", anchor="w",
        )
        self.status_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)

        # Row 6: Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=6, column=0, columnspan=2, sticky="ew")

        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)

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

        # --- Row 2: Subtitle - multi-select Listbox at col 1-2, fmt/embed stacked at col 3 ---
        ttk.Label(f, text=t("label_orig_subtitle")).grid(row=2, column=0, sticky="nw", pady=3)

        sub_list_frame = ttk.Frame(f)
        sub_list_frame.grid(row=2, column=1, columnspan=2, padx=5, pady=3, sticky="ew")
        self._orig_subtitle_listbox = tk.Listbox(
            sub_list_frame, selectmode=tk.MULTIPLE, height=3, exportselection=False,
            state=tk.DISABLED,
        )
        _sub_vsb = ttk.Scrollbar(sub_list_frame, orient="vertical",
                                 command=self._orig_subtitle_listbox.yview)
        self._orig_subtitle_listbox.configure(yscrollcommand=_sub_vsb.set)
        self._orig_subtitle_listbox.pack(side="left", fill="both", expand=True)
        _sub_vsb.pack(side="right", fill="y")
        self._orig_subtitle_listbox.bind("<<ListboxSelect>>", self._on_subtitle_changed)

        sub_right_frame = ttk.Frame(f)
        sub_right_frame.grid(row=2, column=3, padx=5, pady=3, sticky="nw")
        self._orig_subtitle_fmt_var = tk.StringVar(value="srt")
        self._orig_subtitle_fmt_combo = ttk.Combobox(
            sub_right_frame, textvariable=self._orig_subtitle_fmt_var,
            values=_SUBTITLE_FORMATS, state=tk.DISABLED, width=5,
        )
        self._orig_subtitle_fmt_combo.pack(anchor="w")
        self._orig_embed_var = tk.BooleanVar(value=False)
        self._orig_embed_check = ttk.Checkbutton(
            sub_right_frame, text=t("orig_sub_embed"), variable=self._orig_embed_var,
            state=tk.DISABLED,
        )
        self._orig_embed_check.pack(anchor="w", pady=(4, 0))

        f.grid_columnconfigure(1, weight=1)

    # ------------------------------------------------------------------ events

    def _on_format_changed(self, event=None):
        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]
        if format_id == _ORIGINAL_KEY:
            self._original_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
            self.geometry(f"520x{_WIN_H_EXPANDED}")
        else:
            self._original_frame.grid_remove()
            self.geometry(f"520x{_WIN_H_DEFAULT}")

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
        sel = self._orig_subtitle_listbox.curselection()
        has_sub = bool(sel) and bool(self._orig_subtitle_formats)
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
        self._orig_subtitle_listbox.config(state=tk.DISABLED)
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

        self._fetched_title = result.get("title", "")
        self._orig_video_formats = result["video"]
        self._orig_audio_formats = result["audio"]
        self._orig_subtitle_formats = result["subtitles"]

        video_labels = [auto_label] + [lbl for lbl, _, _ in self._orig_video_formats]
        audio_labels = [auto_label] + [lbl for lbl, _ in self._orig_audio_formats]

        self._orig_video_combo.config(values=video_labels, state="readonly")
        self._orig_video_var.set(auto_label)
        self._orig_audio_combo.config(values=audio_labels, state="readonly")
        self._orig_audio_var.set(auto_label)

        self._orig_subtitle_listbox.config(state=tk.NORMAL)
        self._orig_subtitle_listbox.delete(0, tk.END)
        if self._orig_subtitle_formats:
            for lbl, _, _ in self._orig_subtitle_formats:
                self._orig_subtitle_listbox.insert(tk.END, lbl)
        else:
            self._orig_subtitle_listbox.insert(tk.END, t("orig_sub_unavailable"))
            self._orig_subtitle_listbox.config(state=tk.DISABLED)
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
        sel = self._orig_subtitle_listbox.curselection()
        if not sel or not self._orig_subtitle_formats:
            return None

        lang_codes: list[str] = []
        has_manual = False
        has_auto = False
        for idx in sel:
            if 0 <= idx < len(self._orig_subtitle_formats):
                _, lang_code, is_auto = self._orig_subtitle_formats[idx]
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
            'subtitlesformat': self._orig_subtitle_fmt_var.get(),
            'embed': self._orig_embed_var.get(),
        }

    # ---------------------------------------------------------- queue

    def _add_url(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(t("warn_title"), t("warn_no_url"))
            return

        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]

        cookies_path = self._settings.cookies_path or None
        if cookies_path and not os.path.isfile(cookies_path):
            cookies_path = None

        if format_id == _ORIGINAL_KEY:
            format_spec = self._build_original_format_spec()
            subtitle_opts = self._build_original_subtitle_opts()
            if self._orig_video_combo["state"] == "readonly" and self._fetched_title:
                # Formats already fetched — use cached title, add immediately
                self._enqueue_single(url, format_id, selected, format_spec, subtitle_opts, self._fetched_title)
                self.url_entry.delete(0, tk.END)
                return
            # Formats not yet fetched — snapshot current (auto) spec and fetch title in background
            self._start_add_thread(url, cookies_path, format_id, selected, format_spec, subtitle_opts)
        else:
            self._start_add_thread(url, cookies_path, format_id, selected, None, None)

    def _start_add_thread(self, url, cookies_path, format_id, format_label, format_spec, subtitle_opts):
        self.add_button.config(state=tk.DISABLED, text=t("btn_adding"))
        self._update_status(t("status_fetching_title"), 0)
        threading.Thread(
            target=self._run_fetch_for_add,
            args=(url, cookies_path, format_id, format_label, format_spec, subtitle_opts),
            daemon=True,
        ).start()

    def _run_fetch_for_add(self, url, cookies_path, format_id, format_label, format_spec, subtitle_opts):
        try:
            result = self.downloader.fetch_title_or_entries(url, cookies_path)
            self.after(0, self._on_fetch_for_add_done, result, format_id, format_label, format_spec, subtitle_opts)
        except Exception as e:
            self.after(0, self._update_status, f"❌ {e}", 0)
            self.after(0, lambda err=e: messagebox.showerror(
                t("err_title"), t("err_fetch_title").format(error=err),
            ))
        finally:
            self.after(0, lambda: self.add_button.config(state=tk.NORMAL, text=t("btn_add")))

    def _on_fetch_for_add_done(self, result, format_id, format_label, format_spec, subtitle_opts):
        if result['type'] == 'single':
            self._enqueue_single(
                result['url'], format_id, format_label, format_spec, subtitle_opts, result['title'],
            )
            self.url_entry.delete(0, tk.END)
            self._update_status(t("status_title_added"), 0)
        else:
            if format_id == _ORIGINAL_KEY:
                messagebox.showwarning(t("warn_title"), t("warn_playlist_original_fmt"))
                self._update_status(t("status_ready"), 0)
                return
            entries = result['entries']
            if not entries:
                messagebox.showwarning(t("warn_title"), t("warn_playlist_empty"))
                self._update_status(t("status_ready"), 0)
                return

            snap_spec = (
                f"bestvideo[height<={self._settings.video_resolution}]"
                "[ext=mp4]+bestaudio[ext=m4a]/best"
                if format_id == "fmt_720p" else None
            )
            snap_bitrate = self._settings.mp3_bitrate if format_id == "fmt_mp3" else None

            batch: list[tuple[int, _QueueItem]] = []
            for entry in entries:
                self._item_counter += 1
                item = _QueueItem(
                    url=entry['url'],
                    format_id=format_id,
                    format_label=format_label,
                    format_spec=snap_spec,
                    subtitle_opts=None,
                    title=entry['title'],
                    mp3_bitrate=snap_bitrate,
                )
                batch.append((self._item_counter, item))

            with self._queue_lock:
                for _, item in batch:
                    self._queue_items.append(item)

            for no, item in batch:
                short = item.title if len(item.title) <= 45 else item.title[:42] + "..."
                iid = self._queue_tree.insert(
                    "", "end",
                    values=(no, short, format_label, t("queue_status_waiting")),
                )
                item.tree_iid = iid

            self.url_entry.delete(0, tk.END)
            self._update_status(t("status_playlist_added").format(count=len(batch)), 0)

    def _enqueue_single(self, url, format_id, format_label, format_spec, subtitle_opts, title):
        if format_id == "fmt_720p" and format_spec is None:
            format_spec = (
                f"bestvideo[height<={self._settings.video_resolution}]"
                "[ext=mp4]+bestaudio[ext=m4a]/best"
            )
        mp3_bitrate = self._settings.mp3_bitrate if format_id == "fmt_mp3" else None

        self._item_counter += 1
        item = _QueueItem(
            url=url,
            format_id=format_id,
            format_label=format_label,
            format_spec=format_spec,
            subtitle_opts=subtitle_opts,
            title=title,
            mp3_bitrate=mp3_bitrate,
        )
        with self._queue_lock:
            self._queue_items.append(item)

        short = title if len(title) <= 45 else title[:42] + "..."
        iid = self._queue_tree.insert(
            "", "end",
            values=(self._item_counter, short, format_label, t("queue_status_waiting")),
        )
        item.tree_iid = iid

    def _start_queue(self):
        with self._queue_lock:
            has_waiting = any(i.status == "waiting" for i in self._queue_items)

        if not has_waiting:
            messagebox.showwarning(t("warn_title"), t("warn_queue_empty"))
            return

        if self._worker_running:
            return

        self._paused = False
        self._worker_running = True
        self._swap_to_pause_button()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            with self._queue_lock:
                if self._paused:
                    self._worker_running = False
                    self.after(0, self._on_worker_paused)
                    return
                item = next((i for i in self._queue_items if i.status == "waiting"), None)
                if item is None:
                    self._worker_running = False
                    self.after(0, self._on_worker_done)
                    return
                item.status = "downloading"

            self.after(0, self._refresh_tree_item, item)

            def make_cb(qi):
                def cb(text, percent):
                    self._update_status(text, percent)
                    self.after(0, self._refresh_tree_item, qi)
                return cb

            self.downloader.status_callback = make_cb(item)

            cookies_path = self._settings.cookies_path or None
            if cookies_path and not os.path.isfile(cookies_path):
                self.after(0, lambda p=cookies_path: messagebox.showwarning(
                    t("warn_title"), t("warn_cookies_not_found").format(path=p),
                ))
                cookies_path = None

            try:
                self.downloader.download_video(
                    item.url, item.format_id, cookies_path, item.format_spec, item.subtitle_opts,
                    mp3_bitrate_override=item.mp3_bitrate,
                )
                with self._queue_lock:
                    item.status = "done"
            except Exception as e:
                with self._queue_lock:
                    item.status = "error"
                self.after(0, lambda err=e: messagebox.showerror(
                    t("err_title"), t("err_download").format(error=err),
                ))

            self.after(0, self._refresh_tree_item, item)

    def _refresh_tree_item(self, item: _QueueItem):
        if not item.tree_iid or not self._queue_tree.exists(item.tree_iid):
            return
        status_map = {
            "waiting": t("queue_status_waiting"),
            "downloading": t("queue_status_downloading"),
            "done": t("queue_status_done"),
            "error": t("queue_status_error"),
        }
        status_text = status_map.get(item.status, item.status)
        vals = self._queue_tree.item(item.tree_iid, "values")
        tags = (item.status,) if item.status in ("downloading", "done", "error") else ()
        self._queue_tree.item(item.tree_iid, values=(vals[0], vals[1], vals[2], status_text), tags=tags)

    def _pause_queue(self):
        self._paused = True
        self._swap_to_start_button()

    def _on_worker_done(self):
        self._swap_to_start_button()
        self._update_status(t("status_ready"), 0)

    def _on_worker_paused(self):
        # Button already swapped by _pause_queue; nothing else needed
        pass

    def _swap_to_pause_button(self):
        if not self._showing_pause_button:
            self.start_queue_button.pack_forget()
            self.pause_queue_button.pack(side="left", padx=(0, 5), before=self.remove_item_button)
            self._showing_pause_button = True

    def _swap_to_start_button(self):
        if self._showing_pause_button:
            self.pause_queue_button.pack_forget()
            self.start_queue_button.pack(side="left", padx=(0, 5), before=self.remove_item_button)
            self._showing_pause_button = False

    def _remove_selected(self):
        sel = self._queue_tree.selection()
        if not sel:
            return
        iid = sel[0]
        with self._queue_lock:
            item = next((i for i in self._queue_items if i.tree_iid == iid), None)
            if item is None or item.status == "downloading":
                return
            self._queue_items.remove(item)
        self._queue_tree.delete(iid)

    # ----------------------------------------------------------- settings/misc

    def _open_settings(self):
        dialog = SettingsDialog(self, self._settings_manager)
        self.wait_window(dialog)
        self._settings = self._settings_manager.load()
        self.downloader.output_dir = self._resolve_download_path()
        self.downloader.video_resolution = self._settings.video_resolution
        self.downloader.mp3_bitrate = self._settings.mp3_bitrate
        # Rebuild format dropdown labels to reflect updated quality settings
        old_idx = self._format_display.index(self.format_var.get())
        self._format_display = self._build_format_display()
        self.format_combo.config(values=self._format_display)
        self.format_var.set(self._format_display[old_idx])

    def _update_status(self, text, percent):
        self.status_label.config(text=text)
        self.progress_bar["value"] = percent
