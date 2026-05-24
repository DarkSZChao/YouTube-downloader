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
        preview_button.disable()
        download_button.disable()
        download_all.disable()
    else:
        input_url.enable()
        preview_button.enable()
        download_button.enable()
        download_all.enable()


def set_status(message: str, color: str = "green") -> None:
    status_label.style(f"color: {color}; margin-top: 10px").set_text(message)


def clear_tracks() -> None:
    tracks_container.clear()
    playlist_summary.set_text("")
    download_all.visible = False


def render_media_info(media: MediaInfo) -> None:
    clear_tracks()

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
        set_status(f"Unable to read URL: {exc}", "red")
        ui.notify("Unable to read this YouTube URL.", type="negative")
    finally:
        set_busy(False)


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
    set_status(f"Downloading {item_text} and converting to MP3...", "#c56a00")
    ui.notify("Download started. Please keep this page open.")

    try:
        files = await run.cpu_bound(
            download_youtube_as_mp3,
            url,
            str(DOWNLOAD_DIR),
            str(CONFIG["downloads"]["mp3_quality"]),
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
        ui.label("YouTube MP3 Downloader").classes("text-h4")
        input_url = ui.input(
            label="YouTube URL",
            placeholder="https://www.youtube.com/watch?v=... or playlist URL",
        ).style("width: 100%;")

        with ui.row().classes("items-center").style("width: 100%; gap: 12px;"):
            preview_button = ui.button("Check URL", on_click=preview_url).props("outline")
            download_button = ui.button("Download MP3", on_click=download_url)
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
