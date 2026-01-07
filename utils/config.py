from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

class Config:
    def __init__(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"❌ config.yaml nicht gefunden unter {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    @property
    def guild_id(self) -> int:
        return int(self._data.get("guild_id", 0))

    @property
    def roles(self) -> dict:
        return self._data.get("roles", {})

    @property
    def log_channels(self) -> dict:
        return self._data.get("log_channels", {})

# Singleton
config = Config()
