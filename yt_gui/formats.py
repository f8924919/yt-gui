# Internal key → (yt-dlp format spec, is_audio)
FORMAT_SPECS: dict[str, tuple[str, bool]] = {
    "fmt_best_mp4": ("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", False),
    "fmt_720p": ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best", False),
    "fmt_mp3": ("bestaudio/best", True),
    "fmt_original": ("best/best", False),
}

FORMAT_KEYS: list[str] = list(FORMAT_SPECS.keys())
