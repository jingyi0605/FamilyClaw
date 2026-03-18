# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS user-app-builder

WORKDIR /workspace

# 先复制根目录的 package 文件用于安装 workspaces
COPY package.json package-lock.json ./
COPY packages ./packages

# 配置 npm 镜像并安装根目录依赖（包括 workspaces）
RUN npm config set registry https://registry.npmmirror.com \
    && npm ci --legacy-peer-deps --ignore-scripts

# 复制 apps/user-app 并安装其依赖，然后构建
COPY apps/user-app ./apps/user-app
WORKDIR /workspace/apps/user-app
RUN npm ci --legacy-peer-deps && npm run build:h5


FROM python:3.11-bookworm AS runtime

ARG APP_VERSION=0.1.0
ARG BUILD_CHANNEL=development
ARG BUILD_TIME=unknown
ARG GIT_SHA=local
ARG GIT_TAG=
ARG RELEASE_URL=
ARG DOCKER_IMAGE=familyclaw:local

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FAMILYCLAW_APP_VERSION=${APP_VERSION} \
    FAMILYCLAW_BUILD_CHANNEL=${BUILD_CHANNEL} \
    FAMILYCLAW_BUILD_TIME=${BUILD_TIME} \
    FAMILYCLAW_GIT_TAG=${GIT_TAG} \
    FAMILYCLAW_RELEASE_URL=${RELEASE_URL} \
    FAMILYCLAW_RELEASE_MANIFEST_PATH=/opt/familyclaw/release-manifest.json \
    PATH=/usr/lib/postgresql/15/bin:/opt/familyclaw/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        gzip \
        nginx \
        postgresql-15 \
        postgresql-client-15 \
        supervisor \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/familyclaw

COPY VERSION /opt/familyclaw/VERSION
COPY apps/api-server /opt/familyclaw/apps/api-server
COPY apps/open-xiaoai-gateway /opt/familyclaw/apps/open-xiaoai-gateway
COPY docker /opt/familyclaw/docker
COPY --from=user-app-builder /workspace/apps/user-app/dist /opt/familyclaw/apps/user-app/dist

RUN python -m pip install --upgrade pip \
    && pip install -e /opt/familyclaw/apps/api-server \
    && pip install -e /opt/familyclaw/apps/open-xiaoai-gateway \
    && mkdir -p /opt/familyclaw/bin /data/postgres /data/plugins /data/backups /data/logs /data/runtime /data/voice-runtime-artifacts /var/run/postgresql /var/log/familyclaw /var/log/supervisor \
    && chmod +x /opt/familyclaw/docker/scripts/*.sh \
    && ln -sf /opt/familyclaw/docker/scripts/familyclawctl.sh /opt/familyclaw/bin/familyclawctl \
    && rm -f /etc/nginx/sites-enabled/default \
    && rm -f /etc/nginx/conf.d/default.conf \
    && cp /opt/familyclaw/docker/nginx/familyclaw.conf /etc/nginx/conf.d/familyclaw.conf \
    && python /opt/familyclaw/docker/scripts/generate_release_manifest.py \
        --alembic-ini /opt/familyclaw/apps/api-server/alembic.ini \
        --output /opt/familyclaw/release-manifest.json \
        --app-version "${APP_VERSION}" \
        --build-channel "${BUILD_CHANNEL}" \
        --build-time "${BUILD_TIME}" \
        --git-sha "${GIT_SHA}" \
        --git-tag "${GIT_TAG:-v${APP_VERSION}}" \
        --release-url "${RELEASE_URL}" \
        --docker-image "${DOCKER_IMAGE}"

VOLUME ["/data"]

EXPOSE 8080 4399

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=5 CMD ["/opt/familyclaw/docker/scripts/healthcheck.sh"]

CMD ["/usr/bin/supervisord", "-c", "/opt/familyclaw/docker/supervisord.conf", "-n"]
