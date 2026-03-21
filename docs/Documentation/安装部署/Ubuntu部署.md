---
title: Ubuntu部署
docId: zh-2.5
version: v0.1
status: draft
order: 250
outline: deep
---

# Ubuntu部署

## 适用场景

- Ubuntu 20.04/22.04 服务器或云主机。
- 期望稳定运行，可接受使用 Docker 自带 PostgreSQL。

## 推荐方案：Docker 直接跑

1. 安装 Docker（官方脚本示例）：
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```
2. 准备数据目录：
   ```bash
   sudo mkdir -p /srv/familyclaw-data && sudo chown $USER:$USER /srv/familyclaw-data
   ```
3. 运行容器：
   ```bash
   docker run -d \
     --name familyclaw \
     -p 8080:8080 \
     -p 4399:4399 \
     -v /srv/familyclaw-data:/data \
     jingyi0605/familyclaw:latest
   ```
   这里默认用 `latest`，避免每次发版都改部署文档。只有在要精确回滚、复现问题，或者明确锁定版本时，才改成具体标签。
   首次启动会自动把随机数据库密码和语音网关 token 写入 `/srv/familyclaw-data/runtime/secrets/`。
4. 验证：
   - `docker ps` 显示容器 Up。
   - 浏览器访问 `http://服务器IP:8080` 看到登录页。

【配图占位：Ubuntu 终端运行与登录页】

## 需要开机自启？

Docker 默认重启策略未开启，可按需添加 `--restart unless-stopped`；如需 systemd 管理，可在宿主创建 service 包裹同样的 `docker run`/`docker start`，本页不重复造轮子。

## 源码部署

如果你在 Ubuntu 上做二开，直接参考 [源码安装](./源码安装.md) 的步骤，依赖安装可用 apt：

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm postgresql
```

其余命令与源码安装页一致。

## 常见问题

- 8080 访问失败：检查 UFW / 安全组是否放行 8080（及可选 4399）。
- 权限不足：确保 `/srv/familyclaw-data` 对运行用户可写。
- Docker 拉镜像慢：可换国内镜像源后重试。
