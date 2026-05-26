# YouTube Audio Downloader

A small NiceGUI app that downloads a selected YouTube audio stream and saves it as MP3. Playlist URLs are detected, shown as a track list, and downloaded one selected track at a time.

## Local run

Install FFmpeg and Python dependencies, then run:

```bash
pip install -r requirements.txt
python main.py
```

Open `http://localhost:4655`.

## Configuration

Edit `config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 4655

downloads:
  directory: downloads
  cleanup_after_minutes: 60
  cleanup_interval_minutes: 15
  playlist_preview_limit: 50
```

## Docker deployment

Build and run:

```bash
docker compose up -d --build
```

The app is exposed on port `4655` by default. Override the host port with:

```bash
APP_PORT=8080 docker compose up -d --build
```

Downloaded temporary files are stored in `./downloads` and are cleaned automatically according to `config.yaml`.
