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
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:latest
```

安装文档默认使用 `latest`。只有在需要精确回滚、排查旧版本问题，或者要锁定某个发布版时，才手动改成具体版本标签。

参数说明（基于仓库 Dockerfile 与脚本）：

- `8080`：Nginx 反代到前端 H5 与后端 API。
- `4399`：语音网关（open-xiaoai-gateway），不用语音可去掉端口映射。
- `-v /srv/familyclaw-data:/data`：持久化数据库、插件、日志等。

首次启动时，容器会自动生成随机数据库密码和语音网关 token，并写入：
- `/data/runtime/secrets/db-password`
- `/data/runtime/secrets/voice-gateway-token`

如果你明确要接管这两个值，仍然可以手工传 `FAMILYCLAW_DB_PASSWORD` 和 `FAMILYCLAW_VOICE_GATEWAY_TOKEN`；容器会优先使用你传入的值并同步回上面的 secrets 文件。
如果你还额外传了 `FAMILYCLAW_DATABASE_URL`，容器也会把里面的数据库密码同步成同一个值；不要再让 `FAMILYCLAW_DB_PASSWORD` 和连接串密码写成两个不同值，否则旧版本会直接把自己搞挂。

## 启动后验证

1. 等 60 秒，执行 `docker ps`，容器状态应为 `Up`。
2. 浏览器访问 `http://<服务器IP>:8080` 出现登录页即成功。  
   【配图占位：登录页】
3. 初始账号：`user` / `user`（登录后请立即修改）。
4. 如需检查健康：`docker logs familyclaw | tail -n 50`，看到 api-server 启动且无报错。

## 常见问题

- 访问不到 8080：检查防火墙或端口是否被占用。
- 无法启动容器：确认 Docker 拉镜像成功，或清理旧同名容器 `docker rm -f familyclaw`。
- 登录后提示数据库错误：先确认 `/data/runtime/secrets/db-password` 已生成，再确认数据卷可写；如果你自定义过数据库连接，检查 `FAMILYCLAW_DB_PASSWORD` 和 `FAMILYCLAW_DATABASE_URL` 里的密码是否一致。
- Unraid / NAS 上全新部署仍然报 `password authentication failed for user "familyclaw"`：这通常不是旧数据没删干净，而是旧镜像在首次启动时撞上了数据库密码初始化竞态。更新到包含修复的镜像；如果暂时只能用旧镜像，先显式传同一个 `FAMILYCLAW_DB_PASSWORD` 与 `FAMILYCLAW_DATABASE_URL` 规避。
- 语音相关报错但不用语音：可不映射 4399 端口，忽略语音网关日志。

## 需要卸载

```bash
docker rm -f familyclaw
rm -rf /srv/familyclaw-data   # 数据同时清理时再执行
```
