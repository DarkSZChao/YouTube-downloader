# YouTube 音频下载器

[English](README.md)

这是一个使用 NiceGUI 开发的 YouTube 音频下载应用，支持保存为 MP3，以及从播放列表中选择曲目。

## 配置

打开应用的 `/config` 页面，或者点击主页的 Settings 按钮。配置保存在 `config/config.yaml`。

```yaml
downloads:
  cleanup_after_minutes: 60
  cleanup_interval_minutes: 15
  playlist_preview_limit: 50

youtube:
  user_agent: Mozilla/5.0
```

配置约定：

- 常规、非敏感的应用配置放在 `config/config.yaml`，也可以通过 `/config` 页面修改。
- 密码、cookies 等敏感变量只放在项目根目录 `.env`，不要写入 `config/config.yaml`。
- 使用 `.env.example` 作为可提交的模板，真实 `.env` 不得提交到版本库。

```env
ENV_COOKIES="完整的 Netscape cookies.txt 内容"
```

应用会优先读取进程环境变量，再回退读取本地 `.env`。没有 `.env` 时 Docker 也能正常启动。

服务器地址、内部端口、Docker 端口映射和 reload 行为不由配置页面管理。应用固定监听 `0.0.0.0:8000`。

## VPS Docker 部署

在 VPS 安装 Docker Engine 和 Compose 插件后，于项目根目录运行：

```bash
docker compose up -d --build
```

Docker 在 VPS 上发布主机端口 4658，并映射到容器内部端口：

```text
4658:8000
```

修改 docker-compose.yml 中的端口映射后，需要重新创建容器：

```bash
docker compose up -d --force-recreate
```

临时下载文件保存在 `assets/downloads`，并按照 `config/config.yaml` 中的设置自动清理。

## YouTube 检测

YouTube 可能会对 VPS IP 提示需要登录确认。出现这种情况时，请导出 Netscape 格式的浏览器 cookies，并设置固定的 ENV_COOKIES 环境变量。

Docker 镜像包含 FFmpeg、Node.js 和 BgUtils PO Token Provider。使用项目中的 `Dockerfile` 和 `docker-compose.yml` 部署。
