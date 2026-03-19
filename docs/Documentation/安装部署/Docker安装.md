---
title: Docker安装
docId: zh-2.2
version: v0.1
status: draft
order: 220
outline: deep
---

# Docker安装

## 适用场景

- 想最快启动，不准备马上改代码。
- 只有一台支持 Docker 的机器（服务器、NAS、PC 都行）。
- 接受使用容器自带的 PostgreSQL 与 Nginx。

## 准备条件

- 已安装 Docker（支持 Linux / Windows / macOS）。
- 预留端口：`8080`（网页端），`4399`（语音网关，可选）。
- 预留数据目录：例如 `/srv/familyclaw-data`，会映射到容器内 `/data`。
- 至少 2GB 内存。

## 一条命令跑起来

```bash
docker run -d \
  --name familyclaw \
  -p 8080:8080 \
  -p 4399:4399 \
  -e FAMILYCLAW_DB_PASSWORD='change-me' \
  -e FAMILYCLAW_VOICE_GATEWAY_TOKEN='replace-me' \
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:0.1.0
```

参数说明（基于仓库 Dockerfile 与脚本）：

- `8080`：Nginx 反代到前端 H5 与后端 API。
- `4399`：语音网关（open-xiaoai-gateway），不用语音可去掉端口映射。
- `FAMILYCLAW_DB_PASSWORD`：容器内 PostgreSQL 账户密码，必须设置。
- `FAMILYCLAW_VOICE_GATEWAY_TOKEN`：语音网关鉴权 token，语音不用可留默认，但建议替换。
- `-v /srv/familyclaw-data:/data`：持久化数据库、插件、日志等。

【配图占位：Docker 命令与参数解释】

## 启动后验证

1. 等 60 秒，执行 `docker ps`，容器状态应为 `Up`。
2. 浏览器访问 `http://<服务器IP>:8080` 出现登录页即成功。  
   【配图占位：登录页】
3. 初始账号：`user` / `user`（登录后请立即修改）。
4. 如需检查健康：`docker logs familyclaw | tail -n 50`，看到 api-server 启动且无报错。

## 常见问题

- 访问不到 8080：检查防火墙或端口是否被占用。
- 无法启动容器：确认 Docker 拉镜像成功，或清理旧同名容器 `docker rm -f familyclaw`。
- 登录后提示数据库错误：确认 `FAMILYCLAW_DB_PASSWORD` 不为空且数据卷可写。
- 语音相关报错但不用语音：可不映射 4399 端口，忽略语音网关日志。

## 需要卸载

```bash
docker rm -f familyclaw
rm -rf /srv/familyclaw-data   # 数据同时清理时再执行
```
