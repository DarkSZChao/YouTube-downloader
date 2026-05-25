from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",
        "port": 4655,
        "reload": False,
    },
    "downloads": {
        "directory": "downloads",
        "cleanup_after_minutes": 60,
        "cleanup_interval_minutes": 15,
        "playlist_preview_limit": 50,
    },
    "youtube": {
        "user_agent": "Mozilla/5.0",
    },
}


def _merge_config(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise ValueError("config.yaml must contain a YAML mapping at the top level.")

    config = _merge_config(DEFAULT_CONFIG, loaded)
    download_dir = Path(config["downloads"]["directory"])
    if not download_dir.is_absolute():
        download_dir = BASE_DIR / download_dir
    config["downloads"]["directory"] = str(download_dir)
    return config
