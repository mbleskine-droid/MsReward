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

RUN git clone -b v3 https://github.com/TheNetsky/Microsoft-Rewards-Script.git .

# Écriture du script patch dans un fichier, puis exécution
RUN echo 'f="src/util/Utils.ts"' > /tmp/patch.py \
    && echo 'c=open(f).read()' >> /tmp/patch.py \
    && echo 'c=c.replace("import { StringValue } from '\''ms'\'';", "")' >> /tmp/patch.py \
    && echo 'c=c.replace(": StringValue", ": string")' >> /tmp/patch.py \
    && echo 'open(f,"w").write(c)' >> /tmp/patch.py \
    && python3 /tmp/patch.py \
    && printf 'declare module "ms";\ndeclare module "semver";\n' > src/types-shims.d.ts

RUN NODE_ENV=development npm ci \
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
