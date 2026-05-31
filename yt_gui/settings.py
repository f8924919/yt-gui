import json
import os
import sys
from dataclasses import asdict, dataclass
from urllib.parse import quote

PROXY_SCHEMES: tuple[str, ...] = ("http", "https", "socks4", "socks5", "socks5h")

# 並列フラグメント DL 数の指定可能範囲（UI のスピンボックスにも適用）
CONCURRENT_FRAGMENTS_MIN = 1
CONCURRENT_FRAGMENTS_MAX = 16


@dataclass
class Settings:
    cookies_path: str = ""
    cookies_browser: str = ""  # ブラウザ名（空 = ブラウザ未使用）
    download_path: str = ""  # 空文字のときは ~/Downloads を使用
    language: str = "ja"
    video_resolution: str = "720"
    mp3_bitrate: str = "192"
    audio_format: str = "mp3"
    video_container: str = "mp4"
    output_template_video: str = "%(title)s.%(ext)s"
    output_template_playlist: str = (
        "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    )
    concurrent_fragments: int = 1  # 並列フラグメント DL 数（1 = 単一フラグメント）
    proxy_enabled: bool = False
    proxy_scheme: str = "http"
    proxy_host: str = ""
    proxy_port: str = ""
    proxy_username: str = ""
    proxy_password: str = ""


def build_proxy_url(settings: Settings) -> str:
    """yt-dlp の `proxy` オプションに渡せる URL を組み立てて返す。
    `proxy_enabled` が False または `proxy_host` が空のときは空文字を返す。"""
    if not settings.proxy_enabled:
        return ""
    host = settings.proxy_host.strip()
    if not host:
        return ""
    scheme = settings.proxy_scheme.strip() or "http"
    auth = ""
    if settings.proxy_username:
        user = quote(settings.proxy_username, safe="")
        if settings.proxy_password:
            pw = quote(settings.proxy_password, safe="")
            auth = f"{user}:{pw}@"
        else:
            auth = f"{user}@"
    port = settings.proxy_port.strip()
    port_part = f":{port}" if port else ""
    return f"{scheme}://{auth}{host}{port_part}"


def _get_config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "yt-gui")


class SettingsManager:
    def __init__(self):
        self._config_dir = _get_config_dir()
        self._config_file = os.path.join(self._config_dir, "settings.json")

    def load(self) -> Settings:
        if not os.path.isfile(self._config_file):
            return Settings()
        try:
            with open(self._config_file, encoding="utf-8") as f:
                data = json.load(f)
            return Settings(
                **{k: v for k, v in data.items() if k in Settings.__dataclass_fields__}
            )
        except Exception:
            return Settings()

    def save(self, settings: Settings) -> None:
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, ensure_ascii=False, indent=2)
