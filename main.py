import asyncio
import glob
import os
import threading
import time

from nicegui import app, ui, run

from check_validation import is_valid_youtube_url
from downloader import download_youtube_as_mp3

# set default saving dir
DEFAULT_SAVING_DIR = os.path.join(os.getcwd(), "downloads")

# expose the background image dir
app.add_static_files("/static", "static")

# set background
ui.add_head_html("""
<style>
    body {
        background-image: url('/static/background.jpg');
        background-size: cover;
        background-position: center;
        margin: 0;
        font-family: Arial, sans-serif;
    }
    .container {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        padding: 20px;
        max-width: 400px;
        margin: auto;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
    }
    .centered {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100vh;
    }
</style>
""")


# Function to delete files older than a certain time
def delete_old_files():
    current_time = time.time()
    for file in glob.glob(os.path.join(DEFAULT_SAVING_DIR, "*.mp3")):
        if os.path.getmtime(file) < current_time - 60 * 10:  # 1 hour ago
            os.remove(file)
            print(f"Delete file: {file}")

    # Set the timer to run again in 1 hour
    threading.Timer(60 * 3, delete_old_files).start()


# disable the items
def disable_GUI_items():
    input_url.disable()
    button_download.disable()
    # radio_method.disable()


# enable the items
def enable_GUI_items():
    input_url.enable()
    button_download.enable()
    # radio_method.enable()


# use async to keep web GUI alive, put GUi control in this function, use await for backend computation
async def async_callback_button_download():
    # disable the items
    disable_GUI_items()

    # check empty URL
    youtube_url = input_url.value
    if not youtube_url:
        label_info.style('color: red; margin-top: 10px').set_text('Enter URL...')
        ui.notify('Enter URL...')
        return

    # check URL is a single video instead of a list
    youtube_url = input_url.value
    if '&list=' in youtube_url:
        label_info.style('color: red; margin-top: 10px').set_text('Do not put URL of a playlist...')
        ui.notify('Do not put URL of a playlist...')
        return

    # check accessible URL
    label_info.style('color: #FF8C00; margin-top: 10px').set_text('Checking URL...')
    ui.notify('Checking URL...')
    res = await run.cpu_bound(is_valid_youtube_url, youtube_url)
    if not res[0]:
        label_info.style('color: red; margin-top: 10px').set_text(res[1])
        ui.notify(res[1])
        return
    else:
        label_info.style('color: green; margin-top: 10px').set_text(res[1])
        ui.notify(res[1])

    await asyncio.sleep(2)

    # download MP3
    label_info.style('color: red; margin-top: 10px').set_text('Preparing MP3...')
    ui.notify('Preparing MP3...')
    try:
        await run.cpu_bound(download_youtube_as_mp3, youtube_url, DEFAULT_SAVING_DIR)
        await asyncio.sleep(3)
        mp3_list = glob.glob(os.path.join(DEFAULT_SAVING_DIR, "*.mp3"))
        latest_mp3 = max(mp3_list, key=os.path.getctime)
        ui.download(latest_mp3)
        label_info.style('color: green; margin-top: 10px').set_text(f'Finish, MP3 is ready.')
        ui.notify(f'Finish, MP3 is ready.')
    except:
        label_info.style('color: red; margin-top: 10px').set_text('Download fail, pls check URL...')
        ui.notify('Download fail, pls check URL...')

    # enable the items
    enable_GUI_items()


async def async_callback_radio_method():
    # disable the items
    disable_GUI_items()

    # save links input when switch
    global previous_buffer
    saved_link = input_url.value
    input_url.clear()
    input_url.value = previous_buffer
    previous_buffer = saved_link

    label_info.style('color: green; margin-top: 10px').set_text(f'Switch to mode: [{radio_method.value}]')
    ui.notify(f'Switch to {radio_method.value}')
    await asyncio.sleep(1)
    if radio_method_options.index(radio_method.value) == 1:
        label_info.style('color: red; margin-top: 10px').set_text('Downloading the whole playlist will be slow!')
        ui.notify('Downloading the whole playlist will be slow!')
        await asyncio.sleep(2)
    label_info.style('color: green; margin-top: 10px').set_text('Downloader ready...')
    ui.notify('Downloader ready...')

    # enable the items
    enable_GUI_items()


previous_buffer = ''
radio_method_options = ['Single YouTube URL', 'YouTube Playlist URL']

# define GUI items
with ui.card().style('max-width: 800px;').classes('container'):
    with ui.row().style('width: 100%'):
        ui.label("YouTube MP3 Downloader").classes("text-h4 text-center")

    with ui.row().style('width: 100%'):
        radio_method = ui.radio(radio_method_options, value='Single YouTube URL', on_change=async_callback_radio_method).props('inline')
        radio_method.disable()
    with ui.row().style('width: 100%'):
        input_url = ui.input(label="Pls enter YouTube URL",
                             placeholder="https://www.youtube.com/watch?v=example").style('width: 100%;')

    with ui.row().style('width: 100%'):
        label_info = ui.label('Downloader ready...').style('color: green; margin-top: 10px').classes("text-h6 text-center")

    with ui.row().style('width: 100%').classes('justify-end'):
        button_download = ui.button("Download MP3", on_click=async_callback_button_download).style('margin-top: 10px')

if __name__ == '__main__':
    delete_old_files()
    ui.run(reload=False, host="0.0.0.0", port=4655)  # reload=False is necessary for pyinstaller
