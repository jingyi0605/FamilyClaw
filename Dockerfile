FROM node:20-bookworm-slim AS user-app-builder

WORKDIR /workspace

# 先复制根目录的 package 文件用于安装 workspaces
COPY package.json package-lock.json ./
COPY packages ./packages

# 配置 npm 镜像并安装根目录依赖（包括 workspaces）
RUN npm config set registry https://registry.npmmirror.com \
    && npm ci --legacy-peer-deps --ignore-scripts

# 复制 apps/user-app 和构建所需的 builtin 插件
COPY apps/user-app ./apps/user-app
COPY apps/api-server/app/plugins/builtin ./apps/api-server/app/plugins/builtin
WORKDIR /workspace/apps/user-app
RUN npm ci --legacy-peer-deps && npm run build:h5


# Python 依赖构建阶段
FROM python:3.11-slim-bookworm AS python-builder

WORKDIR /build

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境并安装依赖
COPY apps/api-server /build/apps/api-server
COPY apps/open-xiaoai-gateway /build/apps/open-xiaoai-gateway

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip \
    && pip install /build/apps/api-server \
    && pip install /build/apps/open-xiaoai-gateway \
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true


# 运行时镜像
FROM python:3.11-slim-bookworm AS runtime

ARG APP_VERSION=0.1.4
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
    PATH=/opt/venv/bin:/usr/lib/postgresql/15/bin:/opt/familyclaw/bin:${PATH}

# 安装运行时依赖
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
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /opt/familyclaw

# 复制虚拟环境
COPY --from=python-builder /opt/venv /opt/venv

# 复制应用文件（只复制必要文件）
COPY VERSION /opt/familyclaw/VERSION
COPY apps/api-server/app /opt/familyclaw/apps/api-server/app
COPY apps/api-server/alembic.ini /opt/familyclaw/apps/api-server/alembic.ini
COPY apps/api-server/migrations /opt/familyclaw/apps/api-server/migrations
COPY apps/open-xiaoai-gateway/open_xiaoai_gateway /opt/familyclaw/apps/open-xiaoai-gateway/open_xiaoai_gateway
COPY docker /opt/familyclaw/docker
COPY --from=user-app-builder /workspace/apps/user-app/dist /opt/familyclaw/apps/user-app/dist

RUN mkdir -p /opt/familyclaw/bin /data/postgres /data/plugins /data/backups /data/logs /data/runtime /data/voice-runtime-artifacts /var/run/postgresql /var/log/familyclaw /var/log/supervisor \
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

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 CMD ["/opt/familyclaw/docker/scripts/healthcheck.sh"]

CMD ["/usr/bin/supervisord", "-c", "/opt/familyclaw/docker/supervisord.conf", "-n"]
