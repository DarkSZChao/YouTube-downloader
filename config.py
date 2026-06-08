from __future__ import annotations

import base64
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"
ENV_PATH = BASE_DIR / ".env"

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
        "cookies_file": "",
    },
}


def runtime_port() -> int | None:
    port = _env_value("PORT")
    if not port:
        return None
    return int(port)


def _env_value(name: str) -> str | None:
    return os.getenv(name) or _env_file_value(name)


def _env_file_value(name: str) -> str | None:
    if not ENV_PATH.exists():
        return None

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip().strip("'\"")
    return None


def _cookies_file_from_env() -> str:
    cookies_text = _env_value("YOUTUBE_COOKIES_TEXT")
    cookies_base64 = _env_value("YOUTUBE_COOKIES_BASE64")
    if not cookies_text and cookies_base64:
        cookies_text = base64.b64decode(cookies_base64).decode("utf-8")

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
    port = runtime_port()
    if port:
        config["server"]["port"] = port

    download_dir = Path(config["downloads"]["directory"])
    if not download_dir.is_absolute():
        download_dir = BASE_DIR / download_dir
    config["downloads"]["directory"] = str(download_dir)

    cookies_file = _env_value("YOUTUBE_COOKIES_FILE") or _cookies_file_from_env() or str(config["youtube"].get("cookies_file") or "")
    if cookies_file:
        cookies_path = Path(cookies_file)
        if not cookies_path.is_absolute():
            cookies_path = BASE_DIR / cookies_path
        config["youtube"]["cookies_file"] = str(cookies_path)
    else:
        config["youtube"]["cookies_file"] = ""

    return config


def load_config_file() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return deepcopy(DEFAULT_CONFIG)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise ValueError("config.yaml must contain a YAML mapping at the top level.")

    config = _merge_config(DEFAULT_CONFIG, loaded)
    return config


def save_config_file(config: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file, sort_keys=False, allow_unicode=True)
