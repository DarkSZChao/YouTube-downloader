# YouTube Audio Downloader

[中文点我！](README.zh-CN.md)

A NiceGUI app that downloads YouTube audio as MP3 and supports selecting tracks from playlists.

## Local Run

Install FFmpeg and Python dependencies, then run:

```bash
pip install -r requirements.txt
python -m app
```

The app always listens on `http://localhost:8000` when run locally.

## Configuration

Open `/config` from the application or use the Settings button. Settings are stored in `config/config.yaml`.

```yaml
downloads:
  cleanup_after_minutes: 60
  cleanup_interval_minutes: 15
  playlist_preview_limit: 50

youtube:
  user_agent: Mozilla/5.0
```

The application always listens on 0.0.0.0:8000. Server host, internal port, Docker port mapping, and reload behavior are not managed from the application settings page.

For local and Docker runs, Netscape-format cookies can optionally be stored in .env. Docker also starts when this file is absent. Use .env.example as the template. The real .env contains credentials and must not be committed.

## Docker Deployment

Build and run:

```bash
docker compose up -d --build
```

Docker always exposes the application at http://localhost:4655 and maps it to the fixed container port:

```text
4655:8000
```

After changing the mapping in docker-compose.yml, recreate the container:

```bash
docker compose up -d --force-recreate
```

Downloaded temporary files are stored in `assets/downloads` and cleaned according to `config/config.yaml`.

## Render and YouTube Checks

YouTube may reject shared hosting IPs with Sign in to confirm you are not a bot. In that case, export Netscape-format browser cookies and set the fixed ENV_COOKIES environment variable.

The Docker image includes the BgUtils PO Token Provider. Render must deploy this repository with its `Dockerfile`; a Python native runtime will not include that provider.
