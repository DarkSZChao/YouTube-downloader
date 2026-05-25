from __future__ import annotations

import asyncio
import shutil
import threading
import time
import zipfile
from pathlib import Path

from nicegui import app, run, ui

from config import load_config
from downloader import MediaInfo, download_youtube_as_mp3, inspect_youtube_url


CONFIG = load_config()
DOWNLOAD_DIR = Path(CONFIG["downloads"]["directory"])
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
MP3_QUALITY_CHOICES = (64, 96, 128, 160, 192, 256, 320)

app.add_static_files("/static", "static")

ui.add_head_html(
    """
<style>
    body {
        background-image: url('/static/background.jpg');
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
        width: min(760px, 100%);
        background: rgba(255, 255, 255, 0.92);
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
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
</style>
"""
)

current_media: MediaInfo | None = None
current_url = ""
preview_request_id = 0


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


def set_busy(is_busy: bool) -> None:
    if is_busy:
        input_url.disable()
        source_quality_select.disable()
        mp3_quality_select.disable()
        download_button.disable()
        download_all.disable()
    else:
        input_url.enable()
        if current_media is not None and current_media.audio_formats:
            source_quality_select.enable()
            mp3_quality_select.enable()
        download_button.enable()
        download_all.enable()


def set_status(message: str, color: str = "green") -> None:
    status_label.style(f"color: {color}; margin-top: 10px").set_text(message)


def clear_tracks() -> None:
    tracks_container.clear()
    playlist_summary.set_text("")
    download_all.visible = False


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
    if current_media is None:
        return None
    selected_format_id = source_quality_select.value
    for audio_format in current_media.audio_formats:
        if audio_format.format_id == selected_format_id:
            return audio_format.bitrate_kbps
    return current_media.audio_formats[0].bitrate_kbps if current_media.audio_formats else None


def update_mp3_quality_default() -> None:
    mp3_quality_select.set_value(matched_mp3_quality(selected_source_bitrate()))


def clear_audio_options() -> None:
    source_quality_select.set_options({}, value=None)
    source_quality_select.disable()
    mp3_quality_select.set_value(None)
    mp3_quality_select.disable()
    source_quality_hint.set_text("")


def render_audio_options(media: MediaInfo) -> None:
    if not media.audio_formats:
        clear_audio_options()
        source_quality_hint.set_text("No detailed audio quality information was returned.")
        return

    source_options = {
        audio_format.format_id: (
            f"{audio_format.bitrate_kbps:g} kbps | {audio_format.ext} | "
            f"{audio_format.codec} | {format_filesize(audio_format.filesize_bytes)}"
        )
        for audio_format in media.audio_formats
    }
    mp3_options = {str(quality): f"{quality} kbps" for quality in MP3_QUALITY_CHOICES}
    source_quality_select.set_options(source_options, value=media.audio_formats[0].format_id)
    mp3_quality_select.set_options(mp3_options, value=matched_mp3_quality(media.audio_formats[0].bitrate_kbps))
    source_quality_select.enable()
    mp3_quality_select.enable()
    source_quality_hint.set_text("Top 3 audio streams reported by yt-dlp. MP3 quality is matched slightly above the selected source.")


def render_media_info(media: MediaInfo) -> None:
    clear_tracks()
    render_audio_options(media)

    if not media.is_playlist:
        playlist_summary.set_text(f"Single video: {media.title}")
        return

    suffix = " Preview is truncated by config." if media.truncated else ""
    playlist_summary.set_text(f"Playlist: {media.title} | {media.total_count} tracks found.{suffix}")
    download_all.visible = True
    download_all.value = True

    with tracks_container:
        with ui.column().classes("track-list"):
            for index, entry in enumerate(media.entries, start=1):
                ui.label(f"{index}. {entry.title}").classes("track-row")


async def preview_url() -> None:
    global current_media, current_url

    url = (input_url.value or "").strip()
    if not url:
        set_status("Please enter a YouTube URL.", "red")
        ui.notify("Please enter a YouTube URL.", type="warning")
        return

    set_busy(True)
    clear_tracks()
    set_status("Reading YouTube information...", "#c56a00")
    try:
        current_media = await run.cpu_bound(
            inspect_youtube_url,
            url,
            int(CONFIG["downloads"]["playlist_preview_limit"]),
            CONFIG["youtube"].get("user_agent"),
        )
        current_url = url
        render_media_info(current_media)
        set_status("Ready to download.", "green")
    except Exception as exc:
        current_media = None
        current_url = ""
        clear_audio_options()
        set_status(f"Unable to read URL: {exc}", "red")
        ui.notify("Unable to read this YouTube URL.", type="negative")
    finally:
        set_busy(False)


async def handle_url_change() -> None:
    global current_media, current_url, preview_request_id

    preview_request_id += 1
    request_id = preview_request_id
    url = (input_url.value or "").strip()

    current_media = None
    current_url = ""
    clear_tracks()
    clear_audio_options()

    if not url:
        set_status("Downloader ready.", "green")
        return

    if not url.startswith(("http://", "https://")):
        set_status("Enter a complete YouTube URL to inspect it.", "#c56a00")
        return

    await asyncio.sleep(0.35)
    if request_id != preview_request_id or url != (input_url.value or "").strip():
        return

    await preview_url()


def build_zip(files: list[str], title: str) -> str:
    zip_name = "".join(char if char.isalnum() or char in " ._-" else "_" for char in title).strip()
    zip_path = Path(files[0]).parent / f"{zip_name or 'youtube-playlist'}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, arcname=Path(file).name)
    return str(zip_path)


async def download_url() -> None:
    global current_media, current_url

    url = (input_url.value or "").strip()
    if not url:
        set_status("Please enter a YouTube URL.", "red")
        ui.notify("Please enter a YouTube URL.", type="warning")
        return

    if current_media is None or current_url != url:
        await preview_url()
        if current_media is None:
            return

    if current_media.is_playlist and not download_all.value:
        set_status("Playlist detected. Confirm 'Download all tracks' before downloading.", "red")
        ui.notify("Confirm playlist download first.", type="warning")
        return

    set_busy(True)
    item_text = "playlist" if current_media.is_playlist else "video"
    set_status(f"Downloading {item_text} and saving as MP3...", "#c56a00")
    ui.notify("Download started. Please keep this page open.")

    try:
        files = await run.cpu_bound(
            download_youtube_as_mp3,
            url,
            str(DOWNLOAD_DIR),
            source_quality_select.value,
            str(mp3_quality_select.value or matched_mp3_quality(selected_source_bitrate())),
            CONFIG["youtube"].get("user_agent"),
        )
        await asyncio.sleep(0.5)
        if len(files) == 1:
            ui.download(files[0])
            set_status("MP3 is ready. Browser download started.", "green")
        else:
            archive = build_zip(files, current_media.title)
            ui.download(archive)
            set_status(f"{len(files)} MP3 files are ready. ZIP download started.", "green")
    except Exception as exc:
        set_status(f"Download failed: {exc}", "red")
        ui.notify("Download failed. Check the URL or server logs.", type="negative")
    finally:
        set_busy(False)


with ui.element("main").classes("page"):
    with ui.card().classes("panel"):
        ui.label("YouTube Audio Downloader").classes("text-h4")
        input_url = ui.input(
            label="YouTube URL",
            placeholder="https://www.youtube.com/watch?v=... or playlist URL",
            on_change=handle_url_change,
        ).style("width: 100%;")
        input_url.props("debounce=900")

        with ui.row().classes("items-center").style("width: 100%; gap: 12px;"):
            source_quality_select = ui.select(
                {},
                label="YouTube source quality",
                value=None,
                on_change=update_mp3_quality_default,
            ).style("flex: 1 1 360px;")
            mp3_quality_select = ui.select(
                {str(quality): f"{quality} kbps" for quality in MP3_QUALITY_CHOICES},
                label="MP3 quality",
                value=None,
            ).style("width: 180px;")
        source_quality_select.disable()
        mp3_quality_select.disable()
        source_quality_hint = ui.label("").style("color: #555; margin-top: -8px;")

        with ui.row().classes("items-center").style("width: 100%; gap: 12px;"):
            download_button = ui.button("Download Audio", on_click=download_url)
            download_all = ui.checkbox("Download all tracks").style("margin-left: auto;")
            download_all.visible = False

        status_label = ui.label("Downloader ready.").style("color: green; margin-top: 10px").classes("text-subtitle1")
        playlist_summary = ui.label("").style("width: 100%;")
        tracks_container = ui.column().style("width: 100%;")


if __name__ == "__main__":
    cleanup_downloads()
    ui.run(
        reload=bool(CONFIG["server"]["reload"]),
        host=str(CONFIG["server"]["host"]),
        port=int(CONFIG["server"]["port"]),
    )
