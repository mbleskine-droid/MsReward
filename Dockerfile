###############################################################################
# Dockerfile pour Render (Web Service gratuit) - Microsoft Rewards Script v3
#
# 2 fichiers a mettre dans ton repo GitHub :
#   - Dockerfile (celui-ci)
#   - app.py
#
# Variables d'environnement Render (Settings > Environment) :
#   ACCOUNT_1_EMAIL    = ton_email@outlook.com
#   ACCOUNT_1_PASSWORD = ton_mot_de_passe
#   CRON_SCHEDULE      = 0 7,16,20 * * *  (optionnel)
#   RUN_ON_START       = true               (optionnel, defaut: true)
###############################################################################

FROM node:22-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=0 \
    NODE_ENV=production \
    TZ=Europe/Paris \
    FORCE_HEADLESS=1 \
    PYTHONUNBUFFERED=1

# Dependances systeme : Python3, Chromium libs, outils
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

# Cloner la branche v3 du repo
RUN git clone -b v3 https://github.com/TheNetsky/Microsoft-Rewards-Script.git .

# Installer les deps Node, compiler TypeScript, nettoyer
RUN npm ci --ignore-scripts \
    && npm run build \
    && rm -rf node_modules \
    && npm ci --omit=dev --ignore-scripts \
    && npm cache clean --force

# Installer Chromium via Patchright (v3 utilise Patchright, pas Playwright)
RUN npx patchright install --with-deps --only-shell chromium \
    && rm -rf /root/.cache /tmp/* /var/tmp/*

# Creer la structure de config v3 (dist/config/ + symlinks)
RUN mkdir -p ./dist/config ./dist/sessions \
    && ln -sf /usr/src/microsoft-rewards-script/dist/config/config.json ./dist/config.json \
    && ln -sf /usr/src/microsoft-rewards-script/dist/config/accounts.json ./dist/accounts.json

# Config par defaut avec headless=true
RUN if [ -f src/config.example.json ]; then \
        cp src/config.example.json ./dist/config/config.json; \
        jq '.headless = true' ./dist/config/config.json > /tmp/config_tmp.json \
        && mv /tmp/config_tmp.json ./dist/config/config.json; \
    fi

# App Python
WORKDIR /app

RUN pip3 install --no-cache-dir --break-system-packages \
    gradio \
    apscheduler

COPY app.py /app/app.py

# Port Render
ENV PORT=10000
EXPOSE 10000

CMD ["python3", "/app/app.py"]
