FROM node:22-bookworm-slim AS pot-builder

ARG BGUTIL_VERSION=1.3.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${BGUTIL_VERSION}" \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil

WORKDIR /opt/bgutil/server
RUN npm ci \
    && npx tsc


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=pot-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=pot-builder /opt/bgutil /opt/bgutil

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 4655

CMD ["sh", "-c", "node /opt/bgutil/server/build/main.js & sleep 2; exec python main.py"]
