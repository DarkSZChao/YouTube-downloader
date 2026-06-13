# YouTube 音频下载器

[English](README.md)

这是一个使用 NiceGUI 开发的 YouTube 音频下载应用，支持保存为 MP3，以及从播放列表中选择曲目。

## 本地运行

先安装 FFmpeg 和 Python 依赖，然后运行：

```bash
pip install -r requirements.txt
python -m app
```

本地运行时，应用始终监听 `http://localhost:8000`。

## 配置

打开应用的 `/config` 页面，或者点击主页的 Settings 按钮。配置保存在 `config/config.yaml`。

```yaml
server:
  host: 0.0.0.0
  external_port: 4655
  reload: false

downloads:
  directory: assets/downloads
  cleanup_after_minutes: 60
  cleanup_interval_minutes: 15
  playlist_preview_limit: 50

youtube:
  user_agent: Mozilla/5.0
  cookies_env: COOKIES_ENV
```

应用内部端口固定为 `8000`。`server.external_port` 表示 Docker 对外暴露的宿主机端口。通过配置页面保存后，该值会同步到 `.env` 中的 `PORT`。

本地运行时，可以把 Netscape 格式的 cookies 保存到 `.env`。请使用 `.env.example` 作为模板。真实 `.env` 含有账号凭据，不应提交到版本库。

## Docker 部署

构建并运行：

```bash
docker compose up -d --build
```

使用默认配置时，打开 `http://localhost:4655`。Docker 会按以下方式映射端口：

```text
外部端口:8000
```

在配置页面修改外部端口后，需要重新创建容器，Docker 才会应用新的宿主机端口映射：

```bash
docker compose up -d --force-recreate
```

临时下载文件保存在 `assets/downloads`，并按照 `config/config.yaml` 中的设置自动清理。

## 版本号

页面显示的版本号来自 `VERSION`。启用仓库 Git hook：

```bash
git config core.hooksPath .githooks
```

## Render 和 YouTube 检测

YouTube 可能会对共享托管 IP 提示 `Sign in to confirm you're not a bot`。出现这种情况时，请导出 Netscape 格式的浏览器 cookies，并配置 `youtube.cookies_env` 指定的环境变量。

Docker 镜像包含 BgUtils PO Token Provider。Render 必须使用仓库中的 `Dockerfile` 部署，普通 Python 运行环境不会包含该 Provider。
