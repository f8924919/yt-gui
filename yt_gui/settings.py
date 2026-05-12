import json
import os
import sys
from dataclasses import asdict, dataclass


@dataclass
class Settings:
    cookies_path: str = ""
    cookies_browser: str = ""   # ブラウザ名（空 = ブラウザ未使用）
    download_path: str = ""  # 空文字のときは ~/Downloads を使用
    language: str = "ja"
    video_resolution: str = "720"
    mp3_bitrate: str = "192"
    audio_format: str = "mp3"


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
