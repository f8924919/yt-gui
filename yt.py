import tkinter as tk
from tkinter import ttk, messagebox
from yt_dlp import YoutubeDL
import threading
import os
import sys
from os.path import expanduser

# --- 1. 動画形式のオプション定義 ---
# キー（GUIに表示されるテキスト）: 値（yt-dlpのフォーマット指定文字列）
# MP3の場合は、後でPost-processorを使って変換するため、formatは'bestaudio/best'で統一
FORMAT_OPTIONS = {
    "最高画質 (MP4に結合)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
    "720p (MP4に結合)": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best",
    "MP3 (音声のみ・192kbps)": "bestaudio/best",
    "オリジナルの形式": "best/best"
}
# ------------------------------------

# --- yt-dlp ダウンロード処理を担うクラス ---

class Downloader:
    def __init__(self, output_dir="downloads", status_callback=None):
        self.output_dir = output_dir
        self.status_callback = status_callback

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def _progress_hook(self, d):
        """
        yt-dlpのダウンロード進捗を受け取り、GUIを更新するフック関数。
        """
        if self.status_callback is None:
            return

        status = d['status']
        if status == 'finished':
            filename = d.get('filename', 'Unknown File')
            self.status_callback(f"✅ 完了: {os.path.basename(filename)}", 100)
        elif status == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes:
                percent = downloaded_bytes / total_bytes * 100
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                self.status_callback(
                    f"⬇️ ダウンロード中: {d.get('_percent_str', '0.0%')} | 速度: {speed} | 残り: {eta}",
                    percent
                )
            else:
                self.status_callback(f"処理中... {d.get('_percent_str', '')}", 0)
        elif status == 'error':
            self.status_callback(f"❌ エラーが発生しました", 0)
        else:
            self.status_callback(f"状態: {status}...", 0)

    def download_video(self, url, format_key, cookies_path = None):
        """
        指定されたURLの動画を指定された形式でダウンロードします。
        :param format_key: FORMAT_OPTIONSのキー
        """
        try:
            # 選択された形式からyt-dlpのフォーマット指定を取得
            format_spec = FORMAT_OPTIONS.get(format_key)
            _ext = '.exe' if sys.platform == 'win32' else ''
            internal_path_deno = os.path.join(os.path.dirname(__file__), f'deno{_ext}')
            internal_path_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg', f'ffmpeg{_ext}')

            if "MP3" in format_key:
                # 🎵 MP3（音声のみ）の場合のオプション
                ydl_opts = {
                    'format': format_spec,
                    'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                    'noplaylist': True,
                    'progress_hooks': [self._progress_hook],
                    # ダウンロード後にMP3に変換するPost-processor
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192', # 192kbpsで出力
                    }],
                    'js_runtimes': {'deno': {'path': internal_path_deno}},  # JavaScriptランタイムの指定
                    'ffmpeg_location': internal_path_ffmpeg,  # ffmpegのパスを指定
                    'remote_components': ['ejs:github'],
                    'cookies': cookies_path if cookies_path else None,
                }
            else:
                # 🎥 動画（MP4結合）の場合のオプション
                ydl_opts = {
                    'format': format_spec,
                    'merge_output_format': 'mp4', # 動画と音声をMP4ファイルとして結合
                    'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                    'noplaylist': True,
                    'progress_hooks': [self._progress_hook], 
                    'js_runtimes': {'deno': {'path': internal_path_deno}},  # JavaScriptランタイムの指定
                    'ffmpeg_location': internal_path_ffmpeg,  # ffmpegのパスを指定
                    'remote_components': ['ejs:github'],
                    'cookies': cookies_path if cookies_path else None,
                }

            self.status_callback("🔍 情報取得中...", 0)
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
        except Exception as e:
            self.status_callback(f"❌ 致命的なエラー: {str(e)}", 0)
            messagebox.showerror("エラー", f"ダウンロード中にエラーが発生しました:\n{e}")

# --- Tkinter GUIアプリケーションクラス ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI ダウンローダー")
        self.geometry("500x250") # ウィンドウサイズを少し大きく
        
        # UI要素の初期化
        self._create_widgets()
        
        # ダウンローダーインスタンス
        home = expanduser("~")
        download_path = os.path.join(home, "Downloads")
        self.downloader = Downloader(download_path, status_callback=self._update_status)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        # 1. URL入力フィールド
        ttk.Label(main_frame, text="動画URL:").grid(row=0, column=0, sticky='w', pady=5)
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # 2. cookies.txtの入力フィールド
        ttk.Label(main_frame, text="Cookies:").grid(row=1, column=0, sticky='w', pady=5)
        self.cookies_entry = ttk.Entry(main_frame, width=50)
        self.cookies_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        internal_path_cookies = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        self.cookies_entry.insert(0, internal_path_cookies)

        # 3. 形式選択ドロップダウン
        ttk.Label(main_frame, text="形式選択:").grid(row=2, column=0, sticky='w', pady=5)
        
        self.format_var = tk.StringVar(self)
        # 選択肢のリスト（キーのみ）
        format_keys = list(FORMAT_OPTIONS.keys())
        self.format_var.set(format_keys[0]) # デフォルトは最高画質
        
        self.format_combo = ttk.Combobox(main_frame, textvariable=self.format_var, values=format_keys, state="readonly", width=48)
        self.format_combo.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        # 4. ダウンロードボタン
        self.download_button = ttk.Button(main_frame, text="ダウンロード開始", command=self._start_download_thread)
        self.download_button.grid(row=3, column=0, columnspan=2, pady=10)

        # 5. ステータス表示ラベル
        self.status_label = ttk.Label(main_frame, text="URLと形式を選択してください", relief='sunken', anchor='w')
        self.status_label.grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)

        # 6. プログレスバー
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=5, column=0, columnspan=2, sticky='ew')
        
        # グリッドの重み設定
        main_frame.grid_columnconfigure(1, weight=1)

    def _update_status(self, text, percent):
        """
        GUIのステータスラベルとプログレスバーを更新します。
        """
        self.status_label.config(text=text)
        self.progress_bar['value'] = percent

    def _start_download_thread(self):
        """
        ダウンロード処理を別スレッドで開始し、GUIのフリーズを防ぎます。
        """
        url = self.url_entry.get().strip()
        format_key = self.format_var.get()
        cookies_path = self.cookies_entry.get().strip() or None
        
        if not url:
            messagebox.showwarning("警告", "ダウンロードするURLを入力してください。")
            return

        # ボタンを無効化して多重起動を防ぐ
        self.download_button.config(state=tk.DISABLED, text="ダウンロード中...")
        self.url_entry.config(state=tk.DISABLED)
        self.format_combo.config(state=tk.DISABLED)
        self._update_status("ダウンロード準備中...", 0)
        
        # ダウンロード処理を別スレッドで実行
        download_thread = threading.Thread(target=self._run_download, args=(url, format_key,cookies_path,))
        download_thread.start()

    def _run_download(self, url, format_key, cookies_path = None):
        """
        スレッド内で実行されるダウンロード関数。完了後にGUIを復元します。
        """
        self.downloader.download_video(url, format_key, cookies_path)
        
        # ダウンロード完了後、メインスレッドに戻ってボタンを有効化
        self.after(100, lambda: self._reset_gui())

    def _reset_gui(self):
        """
        ダウンロード完了またはエラー後にGUIの状態をリセットします。
        """
        self.download_button.config(state=tk.NORMAL, text="ダウンロード開始")
        self.url_entry.config(state=tk.NORMAL)
        self.format_combo.config(state="readonly")
        
# --- アプリケーションの実行 ---

if __name__ == "__main__":
    # FFmpegがインストールされていることを確認してください。
    # MP3変換や動画の結合にはFFmpegが必要です。
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("致命的なエラー", f"アプリケーションの起動中にエラーが発生しました:\n{e}")