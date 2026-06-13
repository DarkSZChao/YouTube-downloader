from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencc import OpenCC
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


OPENCC_T2S = OpenCC("t2s")
GENERIC_MUSIC_WORDS = {
    "audio",
    "cover",
    "live",
    "lyrics",
    "lyric",
    "music video",
    "mv",
    "official",
    "official audio",
    "official music video",
    "official video",
    "video",
    "完整版",
    "純享版",
    "纯享版",
}


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
        diagnostic_terms = ("PO Token", "provider", "player client", "Skipping client", "formats")
        if any(term.casefold() in message.casefold() for term in diagnostic_terms):
            self.messages.append(message)

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


def _base_ydl_options(user_agent: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": False,
    }
    if user_agent:
        options["http_headers"] = {"User-Agent": user_agent}
    return options


def _extract_info_with_cookie_fallback(
    url: str,
    options: dict[str, Any],
    cookies_file: str | None,
    download: bool,
) -> dict[str, Any] | None:
    no_cookie_error_message = ""
    try:
        with YoutubeDL(dict(options)) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as no_cookie_error:
        if not cookies_file:
            raise
        no_cookie_error_message = str(no_cookie_error)

    cookie_options = dict(options)
    cookie_options["cookiefile"] = cookies_file
    try:
        with YoutubeDL(cookie_options) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as cookie_error:
        cookie_error_message = str(cookie_error)

    pot_options = dict(cookie_options)
    pot_options["verbose"] = True
    pot_options["extractor_args"] = {
        "youtube": {
            "player_client": ["mweb"],
        },
        "youtubepot-bgutilscript": {
            "server_home": ["/opt/bgutil/server"],
        },
    }
    try:
        with YoutubeDL(pot_options) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as pot_error:
        raise DownloadError(
            f"{pot_error}\n"
            f"Cookie attempt with the default YouTube client also failed: {cookie_error_message}\n"
            f"Initial attempt without cookies also failed: {no_cookie_error_message}"
        ) from pot_error


def _format_download_error(exc: Exception, log_messages: list[str] | None = None) -> str:
    log_text = "\n".join(log_messages or [])
    message = f"{log_text}\n{exc}"
    clean_message = str(exc).replace("ERROR: ", "").strip()
    if "getaddrinfo failed" in message or "Temporary failure in name resolution" in message:
        return "Unable to reach this URL. Please check that the YouTube link is valid."
    if "WinError 10051" in message or "Failed to establish a new connection" in message:
        return "Cannot connect to YouTube from this machine. Check that the Python process can access YouTube."
    if "Unsupported URL" in message:
        return "Unsupported URL. Please enter a valid YouTube link."
    if "Traceback" in clean_message:
        return "Unable to read this YouTube URL. Please check the link and try again."
    if log_text:
        return f"{clean_message or 'Unable to read this YouTube URL.'}\n\nyt-dlp diagnostics:\n{log_text}"
    return clean_message or "Unable to read this YouTube URL."


def normalize_youtube_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    return f"https://www.youtube.com/watch?v={url}"


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


def _safe_filename_stem(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:180] or "youtube-audio"


def _to_simplified_chinese(value: str) -> str:
    return OPENCC_T2S.convert(value)


def _clean_music_part(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -_|")
    value = re.sub(r"(?i)\b(official|music video|video|mv|lyrics?|audio|live|cover|完整版|純享版|纯享版)\b", "", value)
    value = re.sub(r"[\(\[【《「]\s*[\)\]】》」]", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -_|")
    return value


def _is_generic_music_part(value: str) -> bool:
    normalized = _clean_music_part(value).casefold()
    raw = re.sub(r"\s+", " ", value).strip(" -_|()[]【】《》「」").casefold()
    return not normalized or normalized in GENERIC_MUSIC_WORDS or raw in GENERIC_MUSIC_WORDS


def _mp3_name_from_info(info: dict[str, Any]) -> str | None:
    title = str(info.get("title") or "").strip()
    track = str(info.get("track") or "").strip()
    artist = str(info.get("artist") or info.get("creator") or "").strip()
    if track and artist and not _is_generic_music_part(track) and not _is_generic_music_part(artist):
        return _safe_filename_stem(_to_simplified_chinese(f"{_clean_music_part(track)} - {_clean_music_part(artist)}"))

    normalized_title = re.sub(r"^\s*[\[【《「\(][^\]】》」\)]{1,40}[\]】》」\)]\s*", "", title)

    bracket_match = re.search(r"^\s*(?P<artist>[^【《「\[\(]{1,80})[【《「\[\(](?P<song>[^】》」\]\)]{1,120})[】》」\]\)]", normalized_title)
    if bracket_match:
        song = _clean_music_part(bracket_match.group("song"))
        artist = _clean_music_part(bracket_match.group("artist"))
        if song and artist:
            return _safe_filename_stem(_to_simplified_chinese(f"{song} - {artist}"))

    dash_match = re.search(r"^\s*(?P<artist>[^-–—|:：]{1,80})\s*[-–—|:：]\s*(?P<song>[^|]{1,140})", normalized_title)
    if dash_match:
        song = _clean_music_part(dash_match.group("song"))
        artist = _clean_music_part(dash_match.group("artist"))
        if song and artist:
            return _safe_filename_stem(_to_simplified_chinese(f"{artist} - {song}"))

    return None


def _rename_mp3_if_music_name_found(file_path: str, info: dict[str, Any] | None) -> str:
    source = Path(file_path)
    target_stem = _mp3_name_from_info(info) if info else None
    if not target_stem:
        target_stem = source.stem
    target_stem = _safe_filename_stem(_to_simplified_chinese(target_stem))
    if target_stem == source.stem:
        return file_path

    target = source.with_name(f"{target_stem}{source.suffix}")
    if target == source:
        return file_path

    counter = 2
    while target.exists():
        target = source.with_name(f"{target_stem} ({counter}){source.suffix}")
        counter += 1

    source.rename(target)
    return str(target)


def _unique_zip_name(zip_file: zipfile.ZipFile, filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = filename
    counter = 2
    while candidate in zip_file.namelist():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def _extract_playlist_audio_formats(
    entries: list[dict[str, Any]],
    user_agent: str | None,
    cookies_file: str | None,
    logger: CapturingLogger,
) -> list[AudioFormat]:
    first_entry_url = normalize_youtube_url(entries[0].get("url") or entries[0].get("webpage_url"))
    if not first_entry_url:
        return []

    detail_options = _base_ydl_options(user_agent)
    detail_options["logger"] = logger
    try:
        first_entry_info = _extract_info_with_cookie_fallback(
            first_entry_url,
            detail_options,
            cookies_file,
            download=False,
        )
    except DownloadError:
        return []
    return _audio_formats_from_info(first_entry_info or {})


def inspect_youtube_audio_formats(
    url: str,
    user_agent: str | None = None,
    cookies_file: str | None = None,
) -> list[AudioFormat]:
    logger = CapturingLogger()
    options = _base_ydl_options(user_agent)
    options["logger"] = logger

    try:
        info = _extract_info_with_cookie_fallback(url, options, cookies_file, download=False)
    except DownloadError as exc:
        raise ValueError(_format_download_error(exc, logger.messages)) from exc

    if not info:
        raise ValueError("Unable to read this YouTube URL.")
    return _audio_formats_from_info(info)


def inspect_youtube_url(
    url: str,
    preview_limit: int = 50,
    user_agent: str | None = None,
    cookies_file: str | None = None,
) -> MediaInfo:
    logger = CapturingLogger()
    options = _base_ydl_options(user_agent)
    options["extract_flat"] = "in_playlist"
    options["logger"] = logger

    try:
        info = _extract_info_with_cookie_fallback(url, options, cookies_file, download=False)
    except DownloadError as exc:
        raise ValueError(_format_download_error(exc, logger.messages)) from exc

    if not info:
        raise ValueError("Unable to read this YouTube URL.")

    entries = [entry for entry in info.get("entries", []) if entry] if info.get("_type") == "playlist" else []
    if entries:
        shown_entries = entries[:preview_limit]
        media_entries = [
            MediaEntry(
                title=entry.get("title") or "Untitled",
                url=normalize_youtube_url(entry.get("url") or entry.get("webpage_url")),
            )
            for entry in shown_entries
        ]
        return MediaInfo(
            title=info.get("title") or "YouTube playlist",
            is_playlist=True,
            entries=media_entries,
            total_count=info.get("playlist_count") or len(entries),
            audio_formats=_extract_playlist_audio_formats(entries, user_agent, cookies_file, logger),
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
    cookies_file: str | None = None,
) -> list[str]:
    job_dir = Path(output_folder) / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        return _download_youtube_as_mp3_to_dir(url, job_dir, source_format_id, mp3_quality, user_agent, cookies_file)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


def _download_youtube_as_mp3_to_dir(
    url: str,
    job_dir: Path,
    source_format_id: str | None = None,
    mp3_quality: str = "192",
    user_agent: str | None = None,
    cookies_file: str | None = None,
) -> list[str]:
    logger = CapturingLogger()
    before_files = {path.resolve() for path in job_dir.glob("*.mp3")}

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

    info = None
    try:
        info = _extract_info_with_cookie_fallback(url, options, cookies_file, download=True)
    except DownloadError as exc:
        raise RuntimeError(_format_download_error(exc, logger.messages)) from exc

    files = sorted(str(path) for path in job_dir.glob("*.mp3") if path.resolve() not in before_files)
    if not files:
        raise RuntimeError("No MP3 file was created.")
    return [_rename_mp3_if_music_name_found(file, info) for file in files]


def download_youtube_selection_as_zip(
    urls: list[str],
    output_folder: str,
    user_agent: str | None = None,
    cookies_file: str | None = None,
) -> str:
    if not urls:
        raise RuntimeError("No playlist tracks were selected.")

    batch_dir = Path(output_folder) / uuid.uuid4().hex
    batch_dir.mkdir(parents=True, exist_ok=True)
    zip_path = batch_dir / "youtube-audio-selection.zip"
    downloaded_files: list[str] = []

    try:
        for url in urls:
            audio_formats = inspect_youtube_audio_formats(url, user_agent, cookies_file)
            best_format = audio_formats[0] if audio_formats else None
            source_format_id = best_format.format_id if best_format else None
            mp3_quality = "192"
            if best_format:
                for quality in (64, 96, 128, 160, 192, 256, 320):
                    if quality > best_format.bitrate_kbps:
                        mp3_quality = str(quality)
                        break
                else:
                    mp3_quality = "320"
            downloaded_files.extend(
                _download_youtube_as_mp3_to_dir(url, batch_dir, source_format_id, mp3_quality, user_agent, cookies_file)
            )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in downloaded_files:
                file_path = Path(file)
                archive.write(file_path, _unique_zip_name(archive, file_path.name))
    except Exception:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise

    return str(zip_path)
