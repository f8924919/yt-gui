VIDEO_RESOLUTIONS: tuple[str, ...] = ("480", "720", "1080", "1440", "2160")
MP3_BITRATES: tuple[str, ...] = ("128", "192", "256", "320")


def build_best_spec(container: str = "mp4") -> str:
    if container == "webm":
        return (
            "bestvideo[ext=webm]+bestaudio[ext=webm]"
            "/bestvideo+bestaudio/best"
        )
    if container == "mkv":
        return "bestvideo+bestaudio/best"
    return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"


def build_720p_spec(resolution: str, container: str = "mp4") -> str:
    if container == "webm":
        return (
            f"bestvideo[height<={resolution}][ext=webm]+bestaudio[ext=webm]"
            f"/bestvideo[height<={resolution}]+bestaudio/best"
        )
    if container == "mkv":
        return (
            f"bestvideo[height<={resolution}]+bestaudio"
            f"/best"
        )
    return (
        f"bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={resolution}]+bestaudio/best"
    )

# Internal key → (yt-dlp format spec, is_audio)
# fmt_720p spec and fmt_mp3 bitrate are overridden at runtime from Settings.
FORMAT_SPECS: dict[str, tuple[str, bool]] = {
    "fmt_best_mp4": (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best", False
    ),
    "fmt_720p": (
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=720]+bestaudio/best",
        False,
    ),
    "fmt_mp3": ("bestaudio/best", True),
    "fmt_original": ("best/best", False),
}

FORMAT_KEYS: list[str] = list(FORMAT_SPECS.keys())

AUDIO_FORMATS: tuple[str, ...] = ("mp3", "flac")
VIDEO_CONTAINERS: tuple[str, ...] = ("mp4", "mkv", "webm")
