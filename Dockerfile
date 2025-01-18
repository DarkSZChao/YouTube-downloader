# 使用官方 Python 基础镜像
FROM python:3.12-slim

# 更新 apt 并安装 FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# 将当前目录的内容复制到容器中
WORKDIR /app
COPY . /app

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 指定运行的入口文件
CMD ["python", "main.py"]
