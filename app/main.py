from __future__ import annotations

import sys
import asyncio
import os
import random
import shutil
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.responses import FileResponse, Response
from nicegui import app, ui

from app.config import load_config, load_config_file, save_config_file
from app.downloader import (
    MediaInfo,
    download_youtube_as_mp3,
    download_youtube_selection_as_zip,
    inspect_youtube_audio_formats,
    inspect_youtube_url,
)


CONFIG = load_config()
DOWNLOAD_DIR = Path(CONFIG["downloads"]["directory"])
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR = Path(__file__).resolve().parents[1]
VERSION_PATH = PROJECT_DIR / "VERSION"
APP_VERSION = VERSION_PATH.read_text(encoding="utf-8").strip() if VERSION_PATH.exists() else "unknown"
MP3_QUALITY_CHOICES = (64, 96, 128, 160, 192, 256, 320)
BACKGROUND_DIR = PROJECT_DIR / "assets" / "background"
BACKGROUND_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
BACKGROUND_ROTATION_SECONDS = 24 * 60 * 60
INTERNAL_PORT = 8000
current_background_path: Path | None = None
current_background_started_at = 0.0

app.add_static_files("/background-files", str(BACKGROUND_DIR))


def list_background_images() -> list[Path]:
    if not BACKGROUND_DIR.exists():
        return []
    return sorted(
        path
        for path in BACKGROUND_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in BACKGROUND_IMAGE_EXTENSIONS
    )


def choose_background_image(force: bool = False) -> Path | None:
    global current_background_path, current_background_started_at

    now = time.time()
    if (
        not force
        and current_background_path is not None
        and current_background_path.exists()
        and now - current_background_started_at < BACKGROUND_ROTATION_SECONDS
    ):
        return current_background_path

    images = list_background_images()
    if not images:
        current_background_path = None
        current_background_started_at = now
        return None

    current_background_path = random.choice(images)
    current_background_started_at = now
    return current_background_path


def rotate_background() -> None:
    choose_background_image(force=True)
    schedule_background_rotation()


def schedule_background_rotation() -> None:
    timer = threading.Timer(BACKGROUND_ROTATION_SECONDS, rotate_background)
    timer.daemon = True
    timer.start()


@app.get("/background/current")
def current_background() -> Response:
    background_path = choose_background_image()
    if background_path is None:
        return Response(status_code=404)
    return FileResponse(
        background_path,
        headers={
            "Cache-Control": "no-store, max-age=0",
        },
    )


choose_background_image(force=True)

ui.add_head_html(
    """
<style>
    body {
        background-image: url('/background/current');
        background-size: cover;
        background-position: center;
        margin: 0;
        font-family: Arial, sans-serif;
    }
    .page {
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 32px 16px;
    }
    .panel {
        width: 760px;
        max-width: calc(100vw - 32px);
        box-sizing: border-box;
        background: rgba(255, 255, 255, 0.92);
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
        display: flex;
        flex-direction: column;
        align-items: stretch;
    }
    .url-input {
        width: 100%;
    }
    .form-grid {
        width: 100%;
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 12px;
    }
    .quality-row {
        width: 100%;
        display: grid;
        grid-template-columns: minmax(0, 1fr) 180px;
        gap: 12px;
        align-items: start;
    }
    .quality-row > * {
        min-width: 0;
        width: 100%;
    }
    .quality-row .q-field {
        width: 100%;
        min-width: 0;
    }
    .track-list {
        width: 100%;
        max-height: 260px;
        overflow: auto;
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.72);
        padding: 8px 12px;
    }
    .track-row {
        padding: 6px 0;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        word-break: break-word;
    }
    .track-row:last-child {
        border-bottom: 0;
    }
    .summary-text {
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    .version-badge {
        position: fixed;
        right: 14px;
        bottom: 10px;
        z-index: 1000;
        color: rgba(255, 255, 255, 0.88);
        background: rgba(0, 0, 0, 0.38);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        line-height: 1.2;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
        user-select: none;
    }
</style>
<script>
    window.addEventListener('load', () => {
        const setBackground = () => {
            document.body.style.backgroundImage = `url('/background/current?ts=${Date.now()}')`;
        };
        setBackground();
        window.setInterval(setBackground, 24 * 60 * 60 * 1000);
    });
</script>
""",
    shared=True,
)

current_media: MediaInfo | None = None
current_url = ""
selected_entry_url = ""
selected_entry_urls: list[str] = []
current_audio_formats = []
preview_request_id = 0
playlist_quality_request_id = 0
playlist_checkboxes = []


def render_version_badge() -> None:
    ui.label(f"version: {APP_VERSION}").classes("version-badge")


def cleanup_downloads() -> None:
    cutoff = time.time() - int(CONFIG["downloads"]["cleanup_after_minutes"]) * 60
    for path in DOWNLOAD_DIR.iterdir():
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"Failed to delete {path}: {exc}")

    interval = int(CONFIG["downloads"]["cleanup_interval_minutes"]) * 60
    timer = threading.Timer(interval, cleanup_downloads)
    timer.daemon = True
    timer.start()


def restart_server() -> None:
    def restart() -> None:
        time.sleep(0.4)
        os.execv(sys.executable, [sys.executable, *sys.argv])

    threading.Thread(target=restart, daemon=True).start()


def to_positive_int(value, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return number


def set_busy(is_busy: bool) -> None:
    if is_busy:
        input_url.disable()
        source_quality_select.disable()
        mp3_quality_select.disable()
        download_button.disable()
        for checkbox in playlist_checkboxes:
            checkbox.disable()
    else:
        input_url.enable()
        if current_media is not None and current_media.audio_formats:
            source_quality_select.enable()
            mp3_quality_select.enable()
        update_download_button_state()
        update_playlist_quality_controls()
        for checkbox in playlist_checkboxes:
            checkbox.enable()


def has_downloadable_media() -> bool:
    return current_media is not None and current_url == (input_url.value or "").strip()


def update_download_button_state() -> None:
    if has_downloadable_media():
        download_button.enable()
    else:
        download_button.disable()


def set_status(message: str, color: str = "green") -> None:
    status_label.style(f"color: {color}; margin-top: 10px; white-space: pre-wrap; word-break: break-word;").set_text(message)


def debug_exception_message(context: str, exc: Exception) -> str:
    traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip()
    return f"{context} failed with {type(exc).__name__}: {exc}\n\n{traceback_text}"


def user_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message or "\n" in message or "Traceback" in message or "Exception in subprocess" in message:
        return "Unable to read this YouTube URL. Please check the link and try again."
    return message


def is_supported_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    host = parsed.netloc.casefold()
    query = parse_qs(parsed.query)
    path = parsed.path.rstrip("/")

    if host in {"youtu.be", "www.youtu.be"}:
        return bool(path and path != "/")

    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        return False

    if path == "/watch":
        return bool(query.get("v") or query.get("list"))
    if path == "/playlist":
        return bool(query.get("list"))
    if path.startswith(("/shorts/", "/live/", "/embed/")):
        return len(path.split("/")) >= 3

    return False


def clear_tracks() -> None:
    global playlist_checkboxes, playlist_quality_request_id

    playlist_quality_request_id += 1
    tracks_container.clear()
    playlist_summary.set_text("")
    playlist_checkboxes = []


def format_filesize(size_bytes: int | None) -> str:
    if not size_bytes:
        return "unknown size"
    size_mb = size_bytes / 1024 / 1024
    return f"{size_mb:.1f} MB"


def matched_mp3_quality(source_bitrate_kbps: float | None) -> str:
    if not source_bitrate_kbps:
        return "192"
    for quality in MP3_QUALITY_CHOICES:
        if quality > source_bitrate_kbps:
            return str(quality)
    return str(MP3_QUALITY_CHOICES[-1])


def selected_source_bitrate() -> float | None:
    if not current_audio_formats:
        return None
    selected_format_id = source_quality_select.value
    for audio_format in current_audio_formats:
        if audio_format.format_id == selected_format_id:
            return audio_format.bitrate_kbps
    return current_audio_formats[0].bitrate_kbps


def update_mp3_quality_default() -> None:
    mp3_quality_select.set_value(matched_mp3_quality(selected_source_bitrate()))


def clear_audio_options() -> None:
    global current_audio_formats

    current_audio_formats = []
    source_quality_select.set_options({}, value=None)
    source_quality_select.disable()
    mp3_quality_select.set_value(None)
    mp3_quality_select.disable()
    source_quality_hint.set_text("")


def update_playlist_quality_controls() -> None:
    if current_media is None or not current_media.is_playlist:
        return
    if len(selected_entry_urls) > 1:
        source_quality_select.disable()
        mp3_quality_select.disable()
        source_quality_hint.set_text("")
    else:
        if current_audio_formats:
            source_quality_select.enable()
            mp3_quality_select.enable()


def set_playlist_selection_busy(is_busy: bool) -> None:
    if is_busy:
        download_button.disable()
        for checkbox in playlist_checkboxes:
            checkbox.disable()
        return

    download_button.enable()
    for checkbox in playlist_checkboxes:
        checkbox.enable()
    update_playlist_quality_controls()


def render_audio_options(media: MediaInfo) -> None:
    render_audio_format_options(media.audio_formats)


def render_audio_format_options(audio_formats) -> None:
    global current_audio_formats

    if not audio_formats:
        clear_audio_options()
        source_quality_hint.set_text("No detailed audio quality information was returned.")
        return

    current_audio_formats = list(audio_formats)
    source_options = {
        audio_format.format_id: (
            f"{audio_format.bitrate_kbps:g} kbps | {audio_format.ext} | "
            f"{audio_format.codec} | {format_filesize(audio_format.filesize_bytes)}"
        )
        for audio_format in audio_formats
    }
    mp3_options = {str(quality): f"{quality} kbps" for quality in MP3_QUALITY_CHOICES}
    source_quality_select.set_options(source_options, value=audio_formats[0].format_id)
    mp3_quality_select.set_options(mp3_options, value=matched_mp3_quality(audio_formats[0].bitrate_kbps))
    source_quality_select.enable()
    mp3_quality_select.enable()
    source_quality_hint.set_text("Top 3 audio streams reported by yt-dlp. MP3 quality is matched slightly above the selected source.")


@ui.page("/config")
def config_page() -> None:
    current_config = load_config_file()

    with ui.element("main").classes("page"):
        with ui.card().classes("panel"):
            with ui.row().classes("items-center justify-between").style("width: 100%; gap: 12px;"):
                ui.label("Configuration").classes("text-h4")
                ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat")

            with ui.element("div").classes("form-grid"):
                ui.label("Server").classes("text-h6").style("margin-top: 8px;")
                server_host = ui.input("Host", value=str(current_config["server"]["host"])).classes("url-input")
                external_port = ui.number(
                    "Docker external port",
                    value=int(current_config["server"]["external_port"]),
                    min=1,
                    max=65535,
                ).classes("url-input")
                ui.label(
                    f"The app always listens on port {INTERNAL_PORT}. Recreate the Docker service after changing "
                    "the external port."
                ).style("color: #555; margin-top: -8px;")
                server_reload = ui.checkbox("Reload while developing", value=bool(current_config["server"]["reload"]))

                ui.label("Downloads").classes("text-h6").style("margin-top: 8px;")
                download_directory = ui.input("Download directory", value=str(current_config["downloads"]["directory"])).classes("url-input")
                cleanup_after = ui.number(
                    "Cleanup files older than minutes",
                    value=int(current_config["downloads"]["cleanup_after_minutes"]),
                    min=1,
                ).classes("url-input")
                cleanup_interval = ui.number(
                    "Cleanup check interval minutes",
                    value=int(current_config["downloads"]["cleanup_interval_minutes"]),
                    min=1,
                ).classes("url-input")
                playlist_limit = ui.number(
                    "Playlist preview limit",
                    value=int(current_config["downloads"]["playlist_preview_limit"]),
                    min=1,
                ).classes("url-input")

                ui.label("YouTube").classes("text-h6").style("margin-top: 8px;")
                user_agent = ui.textarea("User agent", value=str(current_config["youtube"]["user_agent"])).classes("url-input")
                user_agent.props("autogrow")
                cookies_env = ui.input(
                    "Cookies",
                    value=str(current_config["youtube"].get("cookies_env") or "COOKIES_ENV"),
                ).classes("url-input")

            status = ui.label("").style("color: #555; margin-top: 10px")

            restart_dialog = ui.dialog()
            with restart_dialog, ui.card().style("width: 420px; max-width: calc(100vw - 32px);"):
                ui.label("Configuration saved").classes("text-h6")
                ui.label(
                    "Restart the app now to apply runtime settings? Docker external port changes require "
                    "recreating the container."
                )
                with ui.row().classes("justify-end").style("width: 100%; gap: 8px;"):
                    ui.button("Later", on_click=restart_dialog.close).props("flat")
                    ui.button("Restart", icon="refresh", on_click=restart_server)

            def save_settings() -> None:
                try:
                    new_config = {
                        "server": {
                            "host": (server_host.value or "").strip() or "0.0.0.0",
                            "external_port": to_positive_int(external_port.value, "External port"),
                            "reload": bool(server_reload.value),
                        },
                        "downloads": {
                            "directory": (download_directory.value or "").strip() or "assets/downloads",
                            "cleanup_after_minutes": to_positive_int(cleanup_after.value, "Cleanup age"),
                            "cleanup_interval_minutes": to_positive_int(cleanup_interval.value, "Cleanup interval"),
                            "playlist_preview_limit": to_positive_int(playlist_limit.value, "Playlist preview limit"),
                        },
                        "youtube": {
                            "user_agent": (user_agent.value or "").strip(),
                            "cookies_env": (cookies_env.value or "").strip() or "COOKIES_ENV",
                        },
                    }
                    if new_config["server"]["external_port"] > 65535:
                        raise ValueError("External port must be between 1 and 65535.")
                    save_config_file(new_config)
                except ValueError as exc:
                    status.style("color: red; margin-top: 10px").set_text(str(exc))
                    ui.notify(str(exc), type="negative")
                    return

                status.style("color: green; margin-top: 10px").set_text(
                    "Saved to config/config.yaml. The external port was also synced to .env."
                )
                restart_dialog.open()

            with ui.row().classes("items-center").style("width: 100%; gap: 12px; margin-top: 12px;"):
                ui.button("Save", icon="save", on_click=save_settings)

    render_version_badge()


def render_media_info(media: MediaInfo) -> None:
    global selected_entry_url, selected_entry_urls, playlist_checkboxes

    clear_tracks()
    render_audio_options(media)

    if not media.is_playlist:
        selected_entry_url = media.entries[0].url or current_url
        selected_entry_urls = [selected_entry_url] if selected_entry_url else []
        playlist_summary.set_text(f"Single video: {media.title}")
        return

    suffix = " Preview is truncated by config." if media.truncated else ""
    playlist_summary.set_text(f"Playlist: {media.title} | {media.total_count} tracks found. Select tracks to download.{suffix}")
    selected_entry_url = media.entries[0].url or ""
    selected_entry_urls = [selected_entry_url] if selected_entry_url else []
    playlist_checkboxes = []

    with tracks_container:
        with ui.column().classes("track-list"):
            for index, entry in enumerate(media.entries, start=1):
                if not entry.url:
                    continue
                checkbox = ui.checkbox(
                    f"{index}. {entry.title}",
                    value=entry.url == selected_entry_url,
                    on_change=handle_playlist_selection_change,
                ).classes("track-row")
                checkbox.entry_url = entry.url
                playlist_checkboxes.append(checkbox)


async def preview_url() -> None:
    global current_media, current_url, selected_entry_url, selected_entry_urls

    url = (input_url.value or "").strip()
    if not url:
        set_status("Please enter a YouTube URL.", "red")
        ui.notify("Please enter a YouTube URL.", type="warning")
        update_download_button_state()
        return

    if not is_supported_youtube_url(url):
        current_media = None
        current_url = ""
        selected_entry_url = ""
        selected_entry_urls = []
        clear_tracks()
        clear_audio_options()
        set_status("Please enter a valid YouTube video or playlist URL.", "red")
        ui.notify("Enter a valid YouTube video or playlist URL.", type="warning")
        update_download_button_state()
        return

    set_busy(True)
    clear_tracks()
    set_status("Reading YouTube information...", "#c56a00")
    try:
        current_media = await asyncio.to_thread(
            inspect_youtube_url,
            url,
            int(CONFIG["downloads"]["playlist_preview_limit"]),
            CONFIG["youtube"].get("user_agent"),
            CONFIG["youtube"].get("cookies_file"),
        )
        current_url = url
        render_media_info(current_media)
        set_status("Ready to download.", "green")
    except Exception as exc:
        current_media = None
        current_url = ""
        selected_entry_url = ""
        selected_entry_urls = []
        clear_audio_options()
        detailed_error = debug_exception_message("preview_url", exc)
        print(detailed_error)
        set_status(detailed_error, "red")
        ui.notify("Unable to read this YouTube URL. Check the server log and the red error block.", type="negative")
    finally:
        set_busy(False)


async def handle_playlist_selection_change(event) -> None:
    global selected_entry_url, selected_entry_urls, playlist_quality_request_id

    playlist_quality_request_id += 1
    request_id = playlist_quality_request_id

    selected_entry_urls = [checkbox.entry_url for checkbox in playlist_checkboxes if checkbox.value and checkbox.entry_url]
    selected_entry_url = selected_entry_urls[0] if len(selected_entry_urls) == 1 else ""
    update_playlist_quality_controls()

    if len(selected_entry_urls) > 1:
        clear_audio_options()
        update_playlist_quality_controls()
        set_status("Ready to download selected tracks at best available quality.", "green")
        return

    if not selected_entry_url:
        clear_audio_options()
        return

    source_quality_select.disable()
    mp3_quality_select.disable()
    set_playlist_selection_busy(True)
    set_status("Reading selected track audio quality...", "#c56a00")
    try:
        audio_formats = await asyncio.to_thread(
            inspect_youtube_audio_formats,
            selected_entry_url,
            CONFIG["youtube"].get("user_agent"),
            CONFIG["youtube"].get("cookies_file"),
        )
        if request_id != playlist_quality_request_id or len(selected_entry_urls) != 1 or selected_entry_url != selected_entry_urls[0]:
            return
        render_audio_format_options(audio_formats)
        set_status("Ready to download.", "green")
    except Exception as exc:
        if request_id != playlist_quality_request_id:
            return
        clear_audio_options()
        detailed_error = debug_exception_message("handle_playlist_selection_change", exc)
        print(detailed_error)
        set_status(detailed_error, "red")
        ui.notify("Unable to read this track's audio quality. Check the server log and the red error block.", type="negative")
    finally:
        if request_id == playlist_quality_request_id:
            set_playlist_selection_busy(False)


async def handle_url_change() -> None:
    global current_media, current_url, selected_entry_url, selected_entry_urls, preview_request_id

    preview_request_id += 1
    request_id = preview_request_id
    url = (input_url.value or "").strip()

    current_media = None
    current_url = ""
    selected_entry_url = ""
    selected_entry_urls = []
    clear_tracks()
    clear_audio_options()

    if not url:
        set_status("Downloader ready.", "green")
        update_download_button_state()
        return

    if not url.startswith(("http://", "https://")):
        set_status("Enter a complete YouTube URL to inspect it.", "#c56a00")
        update_download_button_state()
        return

    if not is_supported_youtube_url(url):
        set_status("Please enter a valid YouTube video or playlist URL.", "red")
        update_download_button_state()
        return

    await asyncio.sleep(0.35)
    if request_id != preview_request_id or url != (input_url.value or "").strip():
        return

    await preview_url()


async def download_url() -> None:
    global current_media, current_url, selected_entry_url, selected_entry_urls

    url = (input_url.value or "").strip()
    if not url:
        set_status("Please enter a YouTube URL.", "red")
        ui.notify("Please enter a YouTube URL.", type="warning")
        update_download_button_state()
        return

    if not is_supported_youtube_url(url):
        current_media = None
        current_url = ""
        selected_entry_url = ""
        selected_entry_urls = []
        clear_tracks()
        clear_audio_options()
        set_status("Please enter a valid YouTube video or playlist URL.", "red")
        ui.notify("Enter a valid YouTube video or playlist URL.", type="warning")
        update_download_button_state()
        return

    if current_media is None or current_url != url:
        await preview_url()
        if current_media is None:
            return

    selected_urls = selected_entry_urls if current_media.is_playlist else [url]
    if not selected_urls:
        set_status("Please select at least one playlist track before downloading.", "red")
        ui.notify("Select at least one playlist track first.", type="warning")
        return

    set_busy(True)
    item_text = "selected tracks" if current_media.is_playlist and len(selected_urls) > 1 else "selected track" if current_media.is_playlist else "video"
    set_status(f"Downloading {item_text} and saving as MP3...", "#c56a00")
    ui.notify("Download started. Please keep this page open.")

    try:
        if current_media.is_playlist and len(selected_urls) > 1:
            zip_file = await asyncio.to_thread(
                download_youtube_selection_as_zip,
                selected_urls,
                str(DOWNLOAD_DIR),
                CONFIG["youtube"].get("user_agent"),
                CONFIG["youtube"].get("cookies_file"),
            )
            await asyncio.sleep(0.5)
            ui.download(zip_file)
            set_status("ZIP is ready. Browser download started.", "green")
            return

        files = await asyncio.to_thread(
            download_youtube_as_mp3,
            selected_urls[0],
            str(DOWNLOAD_DIR),
            source_quality_select.value,
            str(mp3_quality_select.value or matched_mp3_quality(selected_source_bitrate())),
            CONFIG["youtube"].get("user_agent"),
            CONFIG["youtube"].get("cookies_file"),
        )
        await asyncio.sleep(0.5)
        ui.download(files[0])
        set_status("MP3 is ready. Browser download started.", "green")
    except Exception as exc:
        detailed_error = debug_exception_message("download_url", exc)
        print(detailed_error)
        set_status(detailed_error, "red")
        ui.notify("Download failed. Check the server log and the red error block.", type="negative")
    finally:
        set_busy(False)


@ui.page("/")
def main_page() -> None:
    global input_url, source_quality_select, mp3_quality_select, source_quality_hint
    global download_button, status_label, playlist_summary, tracks_container

    with ui.element("main").classes("page"):
        with ui.card().classes("panel"):
            with ui.row().classes("items-center justify-between").style("width: 100%; gap: 12px;"):
                ui.label("YouTube Audio Downloader").classes("text-h4")
                ui.button("Settings", icon="settings", on_click=lambda: ui.navigate.to("/config")).props("flat")
            with ui.element("div").classes("form-grid"):
                input_url = ui.input(
                    label="YouTube URL",
                    placeholder="https://www.youtube.com/watch?v=... or playlist URL",
                    on_change=handle_url_change,
                ).classes("url-input")
                input_url.props("debounce=900")

                with ui.element("div").classes("quality-row"):
                    source_quality_select = ui.select(
                        {},
                        label="YouTube source quality",
                        value=None,
                        on_change=update_mp3_quality_default,
                    ).style("width: 100%; min-width: 0;")
                    mp3_quality_select = ui.select(
                        {str(quality): f"{quality} kbps" for quality in MP3_QUALITY_CHOICES},
                        label="MP3 quality",
                        value=None,
                    ).style("width: 100%; min-width: 0;")
            source_quality_select.disable()
            mp3_quality_select.disable()
            source_quality_hint = ui.label("").style("color: #555; margin-top: -8px;")

            with ui.row().classes("items-center").style("width: 100%; gap: 12px;"):
                download_button = ui.button("Download Audio", on_click=download_url)
            download_button.disable()

            status_label = ui.label("Downloader ready.").style("color: green; margin-top: 10px").classes("text-subtitle1")
            playlist_summary = ui.label("").classes("summary-text").style("width: 100%;")
            tracks_container = ui.column().style("width: 100%;")

    render_version_badge()


def main() -> None:
    schedule_background_rotation()
    cleanup_downloads()
    ui.run(
        reload=bool(CONFIG["server"]["reload"]),
        host=str(CONFIG["server"]["host"]),
        port=INTERNAL_PORT,
        show=False,
    )


if __name__ == "__main__":
    main()
