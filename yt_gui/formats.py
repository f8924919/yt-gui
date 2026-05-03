FORMAT_OPTIONS: dict[str, tuple[str, bool]] = {
    "最高画質 (MP4に結合)": ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", False),
    "720p (MP4に結合)": ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best", False),
    "MP3 (音声のみ・192kbps)": ("bestaudio/best", True),
    "オリジナルの形式": ("best/best", False),
}
