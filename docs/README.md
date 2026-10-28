# YouTube Audio Downloader

[中文点我！](README.zh-CN.md)

A NiceGUI app that downloads YouTube audio as MP3 and supports selecting tracks from playlists.

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

Configuration policy:

- Store regular, non-sensitive application settings in `config/config.yaml`. These values can also be edited from the `/config` page.
- Store secrets and credentials only in the project-root `.env`, never in `config/config.yaml`.
- Use `.env.example` as the committed template. The real `.env` must not be committed.

```env
ENV_COOKIES="complete Netscape cookies.txt content"
```

The application checks the process environment first and then the local `.env`. Docker also starts when `.env` is absent.

The application always listens on `0.0.0.0:8000`. Server host, internal port, Docker port mapping, and reload behavior are not managed from the application settings page.

## VPS Docker Deployment

Install Docker Engine with the Compose plugin on the VPS, then run from the repository root:

```bash
docker compose up -d --build
```

On the VPS, Docker publishes host port 4658 and maps it to the fixed container port:

```text
4658:8000
```

After changing the mapping in docker-compose.yml, recreate the container:

```bash
docker compose up -d --force-recreate
```

Downloaded temporary files are stored in `assets/downloads` and cleaned according to `config/config.yaml`.

## YouTube Checks

YouTube may reject VPS IPs with Sign in to confirm you are not a bot. In that case, export Netscape-format browser cookies and set the fixed ENV_COOKIES environment variable.

The Docker image includes FFmpeg, Node.js, and the BgUtils PO Token Provider. Use the included `Dockerfile` and `docker-compose.yml` to deploy.
