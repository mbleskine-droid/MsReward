FROM node:24-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=0 \
    NODE_ENV=production \
    TZ=Europe/Paris \
    FORCE_HEADLESS=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    jq \
    tzdata \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /usr/src/microsoft-rewards-script

# Tout en un seul RUN = impossible à cacher partiellement
RUN git clone -b v3 https://github.com/TheNetsky/Microsoft-Rewards-Script.git . \
    && sed -i 's/import { StringValue } from .ms.;//' src/util/Utils.ts \
    && sed -i 's/: StringValue/: string/g' src/util/Utils.ts \
    && printf 'declare module "ms";\ndeclare module "semver";\n' > src/types-shims.d.ts \
    && NODE_ENV=development npm ci \
    && rm -rf dist \
    && npx tsc \
    && rm -rf node_modules \
    && npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force

RUN npx patchright install --with-deps --only-shell chromium \
    && rm -rf /root/.cache /tmp/* /var/tmp/*

RUN mkdir -p ./dist/config ./dist/sessions

RUN if [ -f src/config.example.json ]; then \
        cp src/config.example.json ./dist/config/config.json \
        && jq '.headless = true' ./dist/config/config.json > /tmp/cfg.json \
        && mv /tmp/cfg.json ./dist/config/config.json; \
    fi

WORKDIR /app

RUN pip3 install --no-cache-dir --break-system-packages gradio apscheduler

COPY app.py /app/app.py

ENV PORT=10000
EXPOSE 10000

CMD ["python3", "/app/app.py"]
