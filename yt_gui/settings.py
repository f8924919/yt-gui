import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from urllib.parse import quote

PROXY_SCHEMES: tuple[str, ...] = ("http", "https", "socks4", "socks5", "socks5h")

# ブラウザ拡張連携のローカル受信サーバー（127.0.0.1）。既定ポートが使用中の
# ときは順にフォールバックを試す（docs/spec/features/browser-extension.md）。
EXTENSION_SERVER_DEFAULT_PORT = 8718
EXTENSION_SERVER_PORT_FALLBACKS: tuple[int, ...] = (8719, 8720)

# 並列フラグメント DL 数の指定可能範囲（UI のスピンボックスにも適用）
CONCURRENT_FRAGMENTS_MIN = 1
CONCURRENT_FRAGMENTS_MAX = 16

# 同時ダウンロード数（キューを並行処理するワーカー数）の指定可能範囲
MAX_CONCURRENT_DOWNLOADS_MIN = 1
MAX_CONCURRENT_DOWNLOADS_MAX = 5

# 速度制限の単位（"K" = KB/s, "M" = MB/s）と換算係数（2 進接頭辞）。
# yt-dlp の --limit-rate と同じく K=1024, M=1024*1024 bytes/sec。
RATE_LIMIT_UNITS: tuple[str, ...] = ("K", "M")
RATE_LIMIT_VALUE_MAX = 100000.0
_RATE_LIMIT_UNIT_FACTORS = {"K": 1024, "M": 1024 * 1024}

# SponsorBlock の処理モード（"" = 無効）と対象カテゴリ。
# カテゴリ名は yt-dlp の SponsorBlock カテゴリ ID に対応する。
SPONSORBLOCK_MODES: tuple[str, ...] = ("", "mark", "remove")
SPONSORBLOCK_CATEGORIES: tuple[str, ...] = (
    "sponsor",
    "selfpromo",
    "interaction",
    "intro",
    "outro",
    "filler",
    "music_offtopic",
)
SPONSORBLOCK_DEFAULT_CATEGORIES: tuple[str, ...] = ("sponsor", "selfpromo")


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
    max_concurrent_downloads: int = 1  # 同時ダウンロード数（1 = 逐次）
    concurrent_fragments: int = 1  # 並列フラグメント DL 数（1 = 単一フラグメント）
    rate_limit_value: float = 0.0  # 速度制限値（0 = 無制限）
    rate_limit_unit: str = "M"  # 速度制限の単位（"K" = KB/s, "M" = MB/s）
    sponsorblock_mode: str = ""  # "" = 無効 / "mark" / "remove"
    sponsorblock_categories: list[str] = field(
        default_factory=lambda: list(SPONSORBLOCK_DEFAULT_CATEGORIES)
    )
    proxy_enabled: bool = False
    proxy_scheme: str = "http"
    proxy_host: str = ""
    proxy_port: str = ""
    proxy_username: str = ""
    proxy_password: str = ""
    download_archive_enabled: bool = False  # 既 DL 動画を記録して再 DL をスキップ
    download_archive_path: str = ""  # 空 = 設定ディレクトリの download_archive.txt
    # ブラウザ拡張連携（ローカル受信サーバー）。既定は無効＝オプトイン。
    extension_enabled: bool = False
    extension_port: int = EXTENSION_SERVER_DEFAULT_PORT
    extension_token: str = ""  # 有効化時に生成（空 = 未生成）


def generate_extension_token() -> str:
    """ブラウザ拡張連携の共有トークンを生成する（URL セーフな乱数）。"""
    return secrets.token_urlsafe(32)


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


def build_rate_limit(settings: Settings) -> float:
    """yt-dlp の `ratelimit`（bytes/sec）を組み立てて返す。
    `rate_limit_value` が 0 以下のときは 0.0 を返す（= 無制限、opt を渡さない）。
    未知の単位は "M"（×1024×1024）相当にフォールバックする。"""
    value = settings.rate_limit_value
    if value <= 0:
        return 0.0
    factor = _RATE_LIMIT_UNIT_FACTORS.get(
        settings.rate_limit_unit, _RATE_LIMIT_UNIT_FACTORS["M"]
    )
    return value * factor


def default_download_archive_path() -> str:
    """ダウンロードアーカイブの既定ファイルパス（設定ディレクトリ直下）。"""
    return os.path.join(_get_config_dir(), "download_archive.txt")


def resolve_download_archive_path(settings: Settings) -> str:
    """yt-dlp の `download_archive` に渡す実効パスを返す。

    `download_archive_enabled` が False のときは空文字を返す（= opt を渡さない）。
    有効かつ `download_archive_path` が空のときは設定ディレクトリの既定パスを使う。
    """
    if not settings.download_archive_enabled:
        return ""
    path = settings.download_archive_path.strip()
    return path or default_download_archive_path()


def count_download_archive_entries(path: str) -> int:
    """アーカイブファイルに記録されている件数（非空行数）を返す。

    ファイルが無い・読めない場合は 0 を返す（非致命）。
    """
    if not path:
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


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
