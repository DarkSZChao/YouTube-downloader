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
class AudioFormat:
    format_id: str
    ext: str
    codec: str
    bitrate_kbps: float
    filesize_bytes: int | None = None


@dataclass(frozen=True)
class MediaInfo:
    title: str
    is_playlist: bool
    entries: list[MediaEntry]
    total_count: int
    audio_formats: list[AudioFormat]
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


def _audio_formats_from_info(info: dict[str, Any], limit: int = 3) -> list[AudioFormat]:
    audio_formats: list[AudioFormat] = []
    for media_format in info.get("formats") or []:
        if media_format.get("vcodec") != "none" or media_format.get("acodec") == "none":
            continue
        bitrate = media_format.get("abr") or media_format.get("tbr")
        if not isinstance(bitrate, (int, float)) or bitrate <= 0:
            continue
        audio_formats.append(
            AudioFormat(
                format_id=str(media_format.get("format_id")),
                ext=str(media_format.get("ext") or "unknown"),
                codec=str(media_format.get("acodec") or "unknown"),
                bitrate_kbps=round(float(bitrate), 1),
                filesize_bytes=media_format.get("filesize") or media_format.get("filesize_approx"),
            )
        )

    audio_formats.sort(key=lambda item: item.bitrate_kbps, reverse=True)
    return audio_formats[:limit]


def _extract_playlist_audio_formats(entries: list[dict[str, Any]], user_agent: str | None, logger: CapturingLogger) -> list[AudioFormat]:
    first_entry_url = entries[0].get("url") or entries[0].get("webpage_url")
    if not first_entry_url:
        return []
    if not str(first_entry_url).startswith(("http://", "https://")):
        first_entry_url = f"https://www.youtube.com/watch?v={first_entry_url}"

    detail_options = _base_ydl_options(user_agent)
    detail_options["logger"] = logger
    try:
        with YoutubeDL(detail_options) as detail_ydl:
            first_entry_info = detail_ydl.extract_info(first_entry_url, download=False)
    except DownloadError:
        return []
    return _audio_formats_from_info(first_entry_info or {})


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
            audio_formats=_extract_playlist_audio_formats(entries, user_agent, logger),
            truncated=len(entries) > preview_limit,
        )

    return MediaInfo(
        title=info.get("title") or "YouTube video",
        is_playlist=False,
        entries=[MediaEntry(title=info.get("title") or "YouTube video", url=info.get("webpage_url"))],
        total_count=1,
        audio_formats=_audio_formats_from_info(info),
    )


def download_youtube_as_mp3(
    url: str,
    output_folder: str,
    source_format_id: str | None = None,
    mp3_quality: str = "192",
    user_agent: str | None = None,
) -> list[str]:
    logger = CapturingLogger()
    job_dir = Path(output_folder) / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)

    options = _base_ydl_options(user_agent)
    options["logger"] = logger
    options.update(
        {
            "format": f"{source_format_id}/bestaudio/best" if source_format_id else "bestaudio/best",
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
