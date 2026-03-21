---
title: Windows部署
docId: zh-2.6
version: v0.1
status: draft
order: 260
outline: deep
---

# Windows部署

## 适用场景

- Windows 10/11 本地演示或轻量测试。
- 开发机上想快速跑通网页端。

## 推荐方案：Docker Desktop

1. 安装 Docker Desktop，启用 WSL2 后端。
2. 预留数据目录，例如 `D:\familyclaw-data`。
3. 打开 PowerShell（管理员）运行：
   ```powershell
   docker run -d `
     --name familyclaw `
     -p 8080:8080 `
     -p 4399:4399 `
     -v D:/familyclaw-data:/data `
     jingyi0605/familyclaw:latest
   ```
   这里默认用 `latest`。只有在你要精确回滚、复现旧版本问题，或者明确锁定某个发布版时，才手动改成具体标签。
   （Windows 下卷路径请用 `/` 分隔。首次启动会把随机数据库密码和语音网关 token 写入 `D:/familyclaw-data/runtime/secrets/`）
4. 浏览器访问 `http://localhost:8080` 看到登录页即成功。

【配图占位：Docker Desktop 容器列表】

## 源码方式（可选）

- 推荐在 WSL2 Ubuntu 发行版内按照 [源码安装](./源码安装.md) 步骤执行。
- 也可用原生 Python 3.11 + PostgreSQL，但需自行保证 `psycopg`、Taro、Node 依赖能在 Windows 编译；官方更建议 WSL。

## 常见问题

- 容器起不来：检查 Docker Desktop 已启动且 WSL2 开启。
- 端口被占用：改用 `-p 18080:8080` 等映射。
- 路径映射失败：确认使用正斜杠路径，如 `D:/familyclaw-data:/data`。
