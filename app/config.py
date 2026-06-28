from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
CONFIG_PATH = PROJECT_DIR / "config" / "config.yaml"
ENV_PATH = PROJECT_DIR / ".env"

DEFAULT_CONFIG: dict[str, Any] = {
    "downloads": {
        "cleanup_after_minutes": 60,
        "cleanup_interval_minutes": 15,
        "playlist_preview_limit": 50,
    },
    "youtube": {
        "user_agent": "Mozilla/5.0",
    },
}


def _env_value(name: str) -> str | None:
    return os.getenv(name) or _env_file_value(name)


def _env_file_value(name: str) -> str | None:
    if not ENV_PATH.exists():
        return None

    value = dotenv_values(ENV_PATH).get(name)
    return str(value) if value is not None else None


def _cookies_file_from_env() -> str:
    cookies_text = _env_value("ENV_COOKIES")
    if not cookies_text:
        return ""

    if "\\n" in cookies_text and "\n" not in cookies_text:
        cookies_text = cookies_text.replace("\\n", "\n")

    cookies_path = Path(tempfile.gettempdir()) / "youtube-cookies.txt"
    cookies_path.write_text(cookies_text, encoding="utf-8")
    return str(cookies_path)


def _merge_config(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    config = load_config_file()

    config["youtube"]["cookies_file"] = _cookies_file_from_env()

    return config


def load_config_file() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise ValueError("config/config.yaml must contain a YAML mapping at the top level.")

    config = _merge_config(DEFAULT_CONFIG, loaded)
    return config


def save_config_file(config: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False, allow_unicode=True)
