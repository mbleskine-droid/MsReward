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
    python3-venv \
    git \
    jq \
    tzdata \
    ca-certificates \
    curl \
    libglib2.0-0 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libasound2 \
    libflac12 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgbm1 \
    libdav1d6 \
    libx11-6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libdouble-conversion3 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /usr/src/microsoft-rewards-script

RUN git clone -b v3 https://github.com/TheNetsky/Microsoft-Rewards-Script.git .

RUN npm ci \
    && rm -rf dist \
    && npx tsc \
    && rm -rf node_modules \
    && npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force

RUN npx patchright install --with-deps --only-shell chromium \
    && rm -rf /root/.cache /tmp/* /var/tmp/*

RUN mkdir -p ./dist/config ./dist/sessions \
    && ln -sf /usr/src/microsoft-rewards-script/dist/config/config.json ./dist/config.json \
    && ln -sf /usr/src/microsoft-rewards-script/dist/config/accounts.json ./dist/accounts.json

RUN if [ -f src/config.example.json ]; then \
        cp src/config.example.json ./dist/config/config.json; \
        jq '.headless = true' ./dist/config/config.json > /tmp/config_tmp.json \
        && mv /tmp/config_tmp.json ./dist/config/config.json; \
    fi

WORKDIR /app

RUN pip3 install --no-cache-dir --break-system-packages \
    gradio \
    apscheduler

COPY app.py /app/app.py

ENV PORT=10000
EXPOSE 10000

CMD ["python3", "/app/app.py"]
