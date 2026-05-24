from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


@dataclass(frozen=True)
class MediaEntry:
    title: str
    url: str | None = None


@dataclass(frozen=True)
class MediaInfo:
    title: str
    is_playlist: bool
    entries: list[MediaEntry]
    total_count: int
    truncated: bool = False


class CapturingLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


def _base_ydl_options(user_agent: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": False,
    }
    if user_agent:
        options["http_headers"] = {"User-Agent": user_agent}
    return options


def _format_download_error(exc: Exception, log_messages: list[str] | None = None) -> str:
    log_text = "\n".join(log_messages or [])
    message = f"{log_text}\n{exc}"
    if "WinError 10051" in message or "Failed to establish a new connection" in message:
        return "Cannot connect to YouTube from this machine. Check that the Python process can access YouTube."
    return str(exc).replace("ERROR: ", "").strip() or "Unable to read this YouTube URL."


def inspect_youtube_url(
    url: str,
    preview_limit: int = 50,
    user_agent: str | None = None,
) -> MediaInfo:
    logger = CapturingLogger()
    options = _base_ydl_options(user_agent)
    options["extract_flat"] = "in_playlist"
    options["logger"] = logger

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise ValueError(_format_download_error(exc, logger.messages)) from exc

    if not info:
        raise ValueError("Unable to read this YouTube URL.")

    entries = [entry for entry in info.get("entries", []) if entry] if info.get("_type") == "playlist" else []
    if entries:
        shown_entries = entries[:preview_limit]
        media_entries = [
            MediaEntry(title=entry.get("title") or "Untitled", url=entry.get("url"))
            for entry in shown_entries
        ]
        return MediaInfo(
            title=info.get("title") or "YouTube playlist",
            is_playlist=True,
            entries=media_entries,
            total_count=info.get("playlist_count") or len(entries),
            truncated=len(entries) > preview_limit,
        )

    return MediaInfo(
        title=info.get("title") or "YouTube video",
        is_playlist=False,
        entries=[MediaEntry(title=info.get("title") or "YouTube video", url=info.get("webpage_url"))],
        total_count=1,
    )


def download_youtube_as_mp3(
    url: str,
    output_folder: str,
    mp3_quality: str = "320",
    user_agent: str | None = None,
) -> list[str]:
    logger = CapturingLogger()
    job_dir = Path(output_folder) / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)

    options = _base_ydl_options(user_agent)
    options["logger"] = logger
    options.update(
        {
            "format": "bestaudio/best",
            "outtmpl": {
                "default": str(job_dir / "%(title).200B [%(id)s].%(ext)s"),
                "thumbnail": str(job_dir / "%(title).200B [%(id)s].%(ext)s"),
            },
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": mp3_quality},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
        }
    )

    try:
        with YoutubeDL(options) as ydl:
            result = ydl.download([url])
    except DownloadError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise RuntimeError(_format_download_error(exc, logger.messages)) from exc

    files = sorted(str(path) for path in job_dir.glob("*.mp3"))
    if result != 0 or not files:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise RuntimeError("No MP3 file was created.")
    return files
