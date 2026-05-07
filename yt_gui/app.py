import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
from os.path import expanduser
from dataclasses import dataclass

from .formats import FORMAT_KEYS, build_720p_spec
from .downloader import Downloader
from .original_format_panel import OriginalFormatPanel
from .settings import SettingsManager
from .settings_dialog import SettingsDialog
from . import get_resource_base
from . import i18n
from .i18n import t
from .utils import strip_ansi

_ORIGINAL_KEY = "fmt_original"
_MP3_KEY = "fmt_mp3"
_WIN_H_DEFAULT = 480
_WIN_H_EXPANDED = 700
_INVALID_PATH_CHARS = re.compile(r'[\\/:*?"<>|]')


def _sanitize_folder_name(name: str) -> str:
    name = _INVALID_PATH_CHARS.sub('_', name)
    return name[:100].strip() or "playlist"


@dataclass
class _QueueItem:
    url: str
    format_id: str
    format_label: str
    format_spec: str | None
    subtitle_opts: dict | None
    title: str = ""
    mp3_bitrate: str | None = None  # snapshotted at add time for fmt_mp3
    mp3_thumbnail: bool = False
    remux_only: bool = False
    playlist_folder: str | None = None  # サブフォルダ名（プレイリスト時のみ）
    status: str = "waiting"  # waiting | downloading | done | error
    tree_iid: str = ""


class App(tk.Tk):
    _STATUS_KEY_MAP: dict[str, str] = {
        "waiting": "queue_status_waiting",
        "downloading": "queue_status_downloading",
        "done": "queue_status_done",
        "error": "queue_status_error",
    }

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

        if not self._settings.cookies_path and not self._settings.cookies_browser:
            default = os.path.join(get_resource_base(), "cookies.txt")
            if os.path.isfile(default):
                self._settings.cookies_path = default

        self._queue_items: list[_QueueItem] = []
        self._queue_lock = threading.Lock()
        self._worker_running = False
        self._paused = False
        self._showing_pause_button = False
        self._item_counter = 0

        # Downloader はパネル構築より先に生成する
        self.downloader = Downloader(
            self._resolve_download_path(),
            status_callback=self._update_status,
            video_resolution=self._settings.video_resolution,
            mp3_bitrate=self._settings.mp3_bitrate,
        )

        self._create_menu()
        self._create_widgets()

    def _resolve_download_path(self) -> str:
        path = self._settings.download_path
        return path if path else os.path.join(expanduser("~"), "Downloads")

    def _resolve_cookies(self) -> tuple[str | None, str | None]:
        """(cookies_path, cookies_browser) のタプルを返す。存在しないファイルは None に変換。"""
        browser = self._settings.cookies_browser or None
        if browser:
            return None, browser
        path = self._settings.cookies_path or None
        if path and not os.path.isfile(path):
            path = None
        return path, None

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
        self._original_panel = OriginalFormatPanel(
            main_frame,
            downloader=self.downloader,
            get_url=lambda: self.url_entry.get().strip(),
            get_cookies=self._resolve_cookies,
            update_status=self._update_status,
        )

        # Row 2: MP3 options (hidden initially, shown when MP3 format selected)
        self._mp3_frame = ttk.Frame(main_frame)
        self._mp3_thumb_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self._mp3_frame, text=t("mp3_embed_thumbnail"), variable=self._mp3_thumb_var,
        ).pack(side="left", padx=(5, 0))

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

    # ------------------------------------------------------------------ events

    def _on_format_changed(self, event=None):
        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]
        if format_id == _ORIGINAL_KEY:
            self._original_panel.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
            self._mp3_frame.grid_remove()
            self.geometry(f"520x{_WIN_H_EXPANDED}")
        elif format_id == _MP3_KEY:
            self._original_panel.grid_remove()
            self._mp3_frame.grid(row=2, column=1, sticky="w", pady=(0, 3))
            self.geometry(f"520x{_WIN_H_DEFAULT}")
        else:
            self._original_panel.grid_remove()
            self._mp3_frame.grid_remove()
            self.geometry(f"520x{_WIN_H_DEFAULT}")

    # ---------------------------------------------------------- queue

    def _add_url(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(t("warn_title"), t("warn_no_url"))
            return

        selected = self.format_var.get()
        format_id = FORMAT_KEYS[self._format_display.index(selected)]

        cookies_path, cookies_browser = self._resolve_cookies()

        if format_id == _ORIGINAL_KEY:
            if self._original_panel.is_both_skipped():
                messagebox.showwarning(t("warn_title"), t("warn_skip_both"))
                return
            format_spec = self._original_panel.get_format_spec()
            subtitle_opts = self._original_panel.get_subtitle_opts()
            remux_only = self._original_panel.get_remux_only()
            if self._original_panel.has_formats_loaded():
                # Formats already fetched — use cached title, add immediately
                self._enqueue_single(url, format_id, selected, format_spec, subtitle_opts,
                                     self._original_panel.get_fetched_title(), remux_only=remux_only)
                self.url_entry.delete(0, tk.END)
                return
            # Formats not yet fetched — snapshot current (auto) spec and fetch title in background
            self._start_add_thread(url, cookies_path, cookies_browser, format_id, selected,
                                   format_spec, subtitle_opts, False, remux_only=remux_only)
        else:
            mp3_thumbnail = self._mp3_thumb_var.get() if format_id == _MP3_KEY else False
            self._start_add_thread(url, cookies_path, cookies_browser, format_id, selected,
                                   None, None, mp3_thumbnail)

    def _start_add_thread(self, url, cookies_path, cookies_browser, format_id, format_label,
                          format_spec, subtitle_opts, mp3_thumbnail=False, remux_only=False):
        self.add_button.config(state=tk.DISABLED, text=t("btn_adding"))
        self._update_status(t("status_fetching_title"), 0)
        threading.Thread(
            target=self._run_fetch_for_add,
            args=(url, cookies_path, cookies_browser, format_id, format_label,
                  format_spec, subtitle_opts, mp3_thumbnail, remux_only),
            daemon=True,
        ).start()

    def _run_fetch_for_add(self, url, cookies_path, cookies_browser, format_id, format_label,
                           format_spec, subtitle_opts, mp3_thumbnail=False, remux_only=False):
        try:
            result = self.downloader.fetch_title_or_entries(url, cookies_path, cookies_browser)
            self.after(0, self._on_fetch_for_add_done, result, format_id, format_label,
                       format_spec, subtitle_opts, mp3_thumbnail, remux_only)
        except Exception as e:
            self.after(0, self._update_status, f"❌ {strip_ansi(str(e))}", 0)
            self.after(0, lambda err=e: messagebox.showerror(
                t("err_title"), t("err_fetch_title").format(error=strip_ansi(str(err))),
            ))
        finally:
            self.after(0, lambda: self.add_button.config(state=tk.NORMAL, text=t("btn_add")))

    def _on_fetch_for_add_done(self, result, format_id, format_label, format_spec, subtitle_opts,
                               mp3_thumbnail=False, remux_only=False):
        if result['type'] == 'single':
            self._enqueue_single(
                result['url'], format_id, format_label, format_spec, subtitle_opts,
                result['title'], mp3_thumbnail, remux_only=remux_only,
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

            playlist_folder = _sanitize_folder_name(result.get('title', ''))

            snap_spec = (
                build_720p_spec(self._settings.video_resolution)
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
                    mp3_thumbnail=mp3_thumbnail,
                    playlist_folder=playlist_folder,
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

    def _enqueue_single(self, url, format_id, format_label, format_spec, subtitle_opts, title,
                        mp3_thumbnail=False, remux_only=False):
        if format_id == "fmt_720p" and format_spec is None:
            format_spec = build_720p_spec(self._settings.video_resolution)
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
            mp3_thumbnail=mp3_thumbnail,
            remux_only=remux_only,
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
        self._set_queue_running(True)
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

            cookies_browser = self._settings.cookies_browser or None
            if cookies_browser:
                cookies_path = None
            else:
                cookies_path = self._settings.cookies_path or None
                if cookies_path and not os.path.isfile(cookies_path):
                    self.after(0, lambda p=cookies_path: messagebox.showwarning(
                        t("warn_title"), t("warn_cookies_not_found").format(path=p),
                    ))
                    cookies_path = None

            try:
                output_dir_override = None
                if item.playlist_folder:
                    output_dir_override = os.path.join(
                        self._resolve_download_path(), item.playlist_folder,
                    )
                self.downloader.download_video(
                    item.url, item.format_id, cookies_path, item.format_spec, item.subtitle_opts,
                    mp3_bitrate_override=item.mp3_bitrate,
                    embed_thumbnail=item.mp3_thumbnail,
                    remux_only=item.remux_only,
                    output_dir_override=output_dir_override,
                    cookies_browser=cookies_browser,
                )
                with self._queue_lock:
                    item.status = "done"
            except Exception as e:
                with self._queue_lock:
                    item.status = "error"
                self.after(0, lambda err=e: messagebox.showerror(
                    t("err_title"), t("err_download").format(error=strip_ansi(str(err))),
                ))

            self.after(0, self._refresh_tree_item, item)

    def _refresh_tree_item(self, item: _QueueItem):
        if not item.tree_iid or not self._queue_tree.exists(item.tree_iid):
            return
        status_text = t(self._STATUS_KEY_MAP[item.status]) if item.status in self._STATUS_KEY_MAP else item.status
        vals = self._queue_tree.item(item.tree_iid, "values")
        tags = (item.status,) if item.status in ("downloading", "done", "error") else ()
        self._queue_tree.item(item.tree_iid, values=(vals[0], vals[1], vals[2], status_text), tags=tags)

    def _pause_queue(self):
        self._paused = True
        self._set_queue_running(False)

    def _on_worker_done(self):
        self._set_queue_running(False)
        self._update_status(t("status_ready"), 0)

    def _on_worker_paused(self):
        # Button already swapped by _pause_queue; nothing else needed
        pass

    def _set_queue_running(self, running: bool):
        if running == self._showing_pause_button:
            return
        if running:
            self.start_queue_button.pack_forget()
            self.pause_queue_button.pack(side="left", padx=(0, 5), before=self.remove_item_button)
        else:
            self.pause_queue_button.pack_forget()
            self.start_queue_button.pack(side="left", padx=(0, 5), before=self.remove_item_button)
        self._showing_pause_button = running

    def _remove_selected(self):
        sel = self._queue_tree.selection()
        if not sel:
            return
        for iid in sel:
            with self._queue_lock:
                item = next((i for i in self._queue_items if i.tree_iid == iid), None)
                if item is None or item.status == "downloading":
                    continue
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
