---
title: NAS部署
docId: zh-2.4
version: v0.1
status: draft
order: 240
outline: deep
---

# NAS部署

## 这页要解决什么

- 用 NAS 面板把 FamilyClaw 的官方镜像跑起来，步骤尽量一致。
- 不同 NAS 仅在“点哪个按钮”上有差异，镜像和参数保持一致。

## 共通准备

- 需要 NAS 已安装 Docker（群晖 7.x 的 Container Manager、QNAP Container Station、飞牛 OS、宝塔 Docker 管理器等）。
- 预留端口：`8080`（网页），`4399`（语音网关，选填）。
- 准备持久化目录：NAS 任意可写目录映射到容器 `/data`，例如 `/volume1/docker/familyclaw`.
- 镜像：`jingyi0605/familyclaw:0.1.0`。
- 环境变量：
  - `FAMILYCLAW_DB_PASSWORD`：容器内 PostgreSQL 密码，必填。
  - `FAMILYCLAW_VOICE_GATEWAY_TOKEN`：语音网关 token，可自定义。

## 通用参数（在面板里对应填写）

- 端口映射：
  - `8080 -> 8080`
  - `4399 -> 4399`（如果不用语音，可不映射）
- 卷挂载：`/volume1/docker/familyclaw:/data`（示例路径）
- 环境变量：按上方两项填写。

## 群晖示例（Container Manager）

1. 打开 *Container Manager* → “注册表”，搜索 `jingyi0605/familyclaw:0.1.0` 并下载。
2. 下载完成后在“映像”里点击 *启动容器*。
3. 网络设置里添加端口映射 8080、4399（可选）。
4. 存储设置里添加文件夹映射 `/volume1/docker/familyclaw` → `/data`。
5. 环境变量页添加 `FAMILYCLAW_DB_PASSWORD`、`FAMILYCLAW_VOICE_GATEWAY_TOKEN`。
6. 启动容器。
7. 浏览器访问 `http://<NAS IP>:8080` 出现登录页即成功。

【配图占位：群晖端口映射界面】【配图占位：群晖卷挂载界面】

## QNAP / 其他面板

- 流程与群晖一致：选镜像 → 设置端口 → 设置卷 → 设置环境变量 → 启动。
- 若面板要求网络模式，选择桥接或 Host 皆可，只需保证 8080（和可选的 4399）可被访问。

## 常见问题

- 端口被占用：改用 NAS 上空闲端口，例如 `18080:8080`。
- 容器频繁重启：大多是 `FAMILYCLAW_DB_PASSWORD` 未设置或 `/data` 不可写，检查权限。
- 页面打不开：确认容器运行中，或在日志里查看是否 PostgreSQL 初始化失败。

## 完成标准

- NAS 面板显示容器运行，`http://<NAS IP>:映射端口` 能打开登录页。
- 数据持久化目录（如 `/volume1/docker/familyclaw`）生成 `postgres`、`logs` 等子目录。
