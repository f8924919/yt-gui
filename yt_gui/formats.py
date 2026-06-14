from dataclasses import dataclass

VIDEO_RESOLUTIONS: tuple[str, ...] = ("480", "720", "1080", "1440", "2160")
MP3_BITRATES: tuple[str, ...] = ("128", "192", "256", "320")


def build_best_spec(container: str = "mp4") -> str:
    if container == "webm":
        return "bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best"
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
        return f"bestvideo[height<={resolution}]+bestaudio/best"
    return (
        f"bestvideo[height<={resolution}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={resolution}]+bestaudio/best"
    )


# Internal key → (yt-dlp format spec, is_audio)
# fmt_720p spec and fmt_mp3 bitrate are overridden at runtime from Settings.
FORMAT_SPECS: dict[str, tuple[str, bool]] = {
    "fmt_best_mp4": (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        False,
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


@dataclass(frozen=True)
class ResolvedExtensionFormat:
    """ブラウザ拡張の形式指定を許可値へクランプした結果。

    呼び出し側はこれを ``dataclasses.replace(settings, ...)`` に流して
    ``build_job_spec`` へ渡す。container は拡張から指定できないため持たない。
    """

    format_id: str
    resolution: str
    audio_format: str
    mp3_bitrate: str


def resolve_extension_format(
    fmt: object,
    *,
    default_resolution: str,
    default_audio_format: str,
    default_mp3_bitrate: str,
) -> ResolvedExtensionFormat | None:
    """拡張の形式指定オブジェクトを正規化する pure function（Qt 非依存）。

    返り値が ``None`` のときはアプリ既定形式を使うことを意味する
    （``kind == "app_default"`` / ``fmt`` が dict でない / ``kind`` が未知）。
    ``resolution`` / ``audio_format`` / ``mp3_bitrate`` は許可値
    （``VIDEO_RESOLUTIONS`` / ``AUDIO_FORMATS`` / ``MP3_BITRATES``）へクランプし、
    欠落・未知値は対応する ``default_*`` へフォールバックする。

    対応仕様: docs/spec/features/browser-extension.md#形式指定オブジェクトformat
    """
    if not isinstance(fmt, dict):
        return None

    kind = fmt.get("kind")
    if kind == "best":
        return ResolvedExtensionFormat(
            format_id="fmt_best_mp4",
            resolution=default_resolution,
            audio_format=default_audio_format,
            mp3_bitrate=default_mp3_bitrate,
        )
    if kind == "resolution":
        resolution = fmt.get("resolution")
        if resolution not in VIDEO_RESOLUTIONS:
            resolution = default_resolution
        return ResolvedExtensionFormat(
            format_id="fmt_720p",
            resolution=resolution,
            audio_format=default_audio_format,
            mp3_bitrate=default_mp3_bitrate,
        )
    if kind == "audio":
        audio_format = fmt.get("audio_format")
        if audio_format not in AUDIO_FORMATS:
            audio_format = default_audio_format
        mp3_bitrate = fmt.get("mp3_bitrate")
        if mp3_bitrate not in MP3_BITRATES:
            mp3_bitrate = default_mp3_bitrate
        return ResolvedExtensionFormat(
            format_id="fmt_mp3",
            resolution=default_resolution,
            audio_format=audio_format,
            mp3_bitrate=mp3_bitrate,
        )
    # app_default / 未知 kind / kind 欠落 → アプリ既定形式
    return None
