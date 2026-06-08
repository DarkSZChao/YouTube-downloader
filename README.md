# YouTube Audio Downloader

[中文说明](README.zh-CN.md)

A small NiceGUI app that downloads a selected YouTube audio stream and saves it as MP3. Playlist URLs are detected, shown as a track list, and downloaded one selected track at a time.

## Local run

Install FFmpeg and Python dependencies, then run:

```bash
pip install -r requirements.txt
python main.py
```

Open `http://localhost:4655`.

## Configuration

Open `http://localhost:4655/config` or use the Settings button on the main page. Saving writes the values to `config.yaml` and asks whether to restart the service.

```yaml
server:
  host: 0.0.0.0
  port: 4655

downloads:
  directory: downloads
  cleanup_after_minutes: 60
  cleanup_interval_minutes: 15
  playlist_preview_limit: 50

youtube:
  user_agent: Mozilla/5.0
  cookies_file: youtube-cookies.txt
```

`youtube.cookies_file` is optional. It points to a Netscape-format cookies file exported from a browser that can access YouTube.

## Docker deployment

Build and run:

```bash
docker compose up -d --build
```

The page shows the version from the committed `VERSION` file. Enable the repository Git hook once on your development machine so each commit updates and stages `VERSION` automatically:

```bash
git config core.hooksPath .githooks
```

If you need the version number to update automatically, add `hooksPath = .githooks` under the `[core]` section in `.git/config`.

After that, normal commits will update the badge value, for example `version: 2026-05-29 18:44`.

The app is exposed on port `4655` by default. Change the single project port in `.env`:

```env
PORT=18080
```

When running in Docker, the service port is controlled by `PORT` in `.env`, not by the config page. After changing `.env`, recreate the container:

```bash
docker compose down
docker compose up -d --build
```

Downloaded temporary files are stored in `./downloads` and are cleaned automatically according to `config.yaml`.

## Render and YouTube bot checks

YouTube may block Render's shared outbound IPs with `Sign in to confirm you're not a bot`. When that happens, yt-dlp needs browser cookies.

Export YouTube cookies in Netscape format, then configure one of these Render environment variables:

```env
YOUTUBE_COOKIES_TEXT=<full cookies.txt content>
```

If Render's editor has trouble with multiline values, base64-encode the whole cookies file and use:

```env
YOUTUBE_COOKIES_BASE64=<base64 encoded cookies.txt content>
```

You can also mount or create a file yourself and point to it:

```env
YOUTUBE_COOKIES_FILE=/path/to/youtube-cookies.txt
```

After changing environment variables, redeploy the Render service.
