# YouTube 音频下载器

[English](README.md)

这是一个小型 NiceGUI 应用，用于下载指定 YouTube 音频流并保存为 MP3。应用可以识别播放列表 URL，显示曲目列表，并一次下载一个选中的曲目。

## 本地运行

先安装 FFmpeg 和 Python 依赖，然后运行：

```bash
pip install -r requirements.txt
python main.py
```

打开 `http://localhost:4655`。

## 配置

打开 `http://localhost:4655/config`，或者在主页点击 Settings 按钮。保存配置会写入 `config.yaml`，并询问是否重启服务。

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

`youtube.cookies_file` 是可选项，填写从能正常访问 YouTube 的浏览器导出的 Netscape 格式 cookies 文件路径。

## Docker 部署

构建并运行：

```bash
docker compose up -d --build
```

页面版本号来自已提交的 `VERSION` 文件。若需要每次 commit 自动更新并暂存 `VERSION`，请在开发机上启用仓库 Git hook：

```bash
git config core.hooksPath .githooks
```

也可以手动在 `.git/config` 的 `[core]` 下添加：

```ini
hooksPath = .githooks
```

之后正常提交时会自动更新页面右下角版本号，例如 `version: 2026-05-29 18:44`。

应用默认暴露在 `4655` 端口。可以用下面的方式覆盖宿主机端口：

```env
PORT=18080
```

Docker 运行时，服务端口由 `.env` 里的 `PORT` 控制，而不是配置页面。容器已创建后如果要修改暴露端口，需要重新创建容器：

```bash
docker compose down
docker compose up -d --build
```

临时下载文件会保存在 `./downloads`，并按照 `config.yaml` 中的设置自动清理。

## Render 和 YouTube 机器人检查

Render 的共享出口 IP 可能被 YouTube 提示 `Sign in to confirm you're not a bot`。出现这个错误时，yt-dlp 需要浏览器 cookies。

先把 YouTube cookies 导出为 Netscape 格式，然后在 Render 添加下面任意一个环境变量：

```env
YOUTUBE_COOKIES_TEXT=<完整 cookies.txt 内容>
```

如果 Render 的环境变量编辑器不方便填写多行内容，可以把整个 cookies 文件做 base64 编码，然后使用：

```env
YOUTUBE_COOKIES_BASE64=<base64 编码后的 cookies.txt 内容>
```

如果你自己创建或挂载了 cookies 文件，也可以直接指定路径：

```env
YOUTUBE_COOKIES_FILE=/path/to/youtube-cookies.txt
```

修改环境变量后，需要重新部署 Render 服务。
