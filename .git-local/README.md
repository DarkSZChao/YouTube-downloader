# 本地 Git 配置

- `install.ps1`：安装当前仓库的本地 Git 配置，并启用自定义提交钩子。
- `config`：让 Git 在当前仓库中区分文件名大小写。
- `hooks/pre-commit`：提交前将当前时间写入根目录下的 `VERSION` 文件并自动暂存。
