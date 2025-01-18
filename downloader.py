from yt_dlp import YoutubeDL
from rename import mp3_rename


def get_youtube_video_title(url):
    with YoutubeDL({'quiet': True}) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        return info_dict.get('title', 'unknown_title')  # get title


def download_youtube_as_mp3(url, output_folder="downloads"):
    options = {
        'format'        : 'bestaudio/best',
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'},
            {'key': 'EmbedThumbnail'},  # embed the image
        ],
        'writethumbnail': True,
        'quiet'         : False,
        # 'cookiefile': './cookie.txt',  # load cookie to overcome age limit
    }
    try:
        options['outtmpl'] = f'{output_folder}/{mp3_rename(get_youtube_video_title(url))}.%(ext)s'
    except:
        options['outtmpl'] = f'{output_folder}/%(title)s.%(ext)s'

    with YoutubeDL(options) as ydl:
        ydl.download([url])


if __name__ == '__main__':
    youtube_url = 'https://www.youtube.com/watch?v=mQmiZgAsgsg&list=PLqhWfUrUxl_l5mpjLY7VafmQYHvaEFIpz'
    download_youtube_as_mp3(youtube_url)
