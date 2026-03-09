# 家庭版 OpenClaw 本地启动与联调说明 v0.1

## 1. 目标

本文档用于帮助新成员在 30 分钟内完成以下动作：

- 启动后端服务
- 初始化 SQLite 数据库与迁移
- 写入演示用模拟数据
- 启动管理台
- 配置并联调 Home Assistant 设备同步

---

## 2. 当前工程结构

核心目录如下：

- `apps/api-server`：FastAPI 后端
- `apps/admin-web`：Vite + React 管理台
- `apps/start-api-server.sh`：后端启动脚本，自动处理 venv、依赖、迁移与热重载
- `apps/seed-api-server.sh`：演示数据种子脚本
- `apps/start-admin-web.sh`：前端启动脚本，自动检查依赖并支持热重载
- `specs/001-家庭底座与成员中心/docs/家庭版OpenClaw-首批接口文档-v0.1.md`：首批接口文档

---

## 3. 环境要求

本地建议环境：

- Python `3.11`
- Node.js `18+`
- npm `9+`

首期数据库固定使用：

- SQLite

当前阶段范围仅限：

- 家庭底座
- 成员中心
- 房间与设备
- 审计日志
- Home Assistant 设备同步

未纳入首期联调范围：

- 问答
- 长期记忆
- 语音
- 复杂场景编排

---

## 4. 后端启动

### 4.1 配置环境变量

在 `apps/api-server` 下创建本地 `.env`：

```bash
cp apps/api-server/.env.example apps/api-server/.env
```

建议至少确认以下变量：

```env
FAMILYCLAW_DATABASE_URL=sqlite:///./data/familyclaw.db
FAMILYCLAW_HOME_ASSISTANT_BASE_URL=http://127.0.0.1:8123
FAMILYCLAW_HOME_ASSISTANT_TOKEN=replace-with-your-token
FAMILYCLAW_HOME_ASSISTANT_TIMEOUT_SECONDS=10
```

说明：

- `.env` 已被忽略，不应提交到仓库
- 如需接入真实 HA，请替换 `BASE_URL` 与 `TOKEN`

### 4.2 启动命令

在仓库根目录执行：

```bash
./apps/start-api-server.sh
```

脚本会自动完成：

- 检测 `python3.11`
- 创建 `apps/api-server/.venv`
- 依据 `pyproject.toml` 检查并安装依赖
- 执行 `alembic upgrade head`
- 以热重载模式启动 `uvicorn`

默认地址：

- `http://0.0.0.0:8000`

常用覆盖参数：

```bash
HOST=0.0.0.0 PORT=8000 ./apps/start-api-server.sh
```

### 4.3 基础验证

```bash
curl http://127.0.0.1:8000/api/v1/healthz
curl http://127.0.0.1:8000/
```

预期：

- 两个接口均可返回 `status: ok`

---

## 5. SQLite 与迁移验证

### 5.1 执行迁移

若只想单独执行迁移：

```bash
cd apps/api-server
source .venv/bin/activate
alembic upgrade head
```

### 5.2 查看 SQLite 文件

默认数据库文件位置：

- `apps/api-server/data/familyclaw.db`

### 5.3 验证表已创建

可使用 `sqlite3`：

```bash
sqlite3 apps/api-server/data/familyclaw.db ".tables"
```

预期至少包含：

- `households`
- `members`
- `member_relationships`
- `member_preferences`
- `member_permissions`
- `rooms`
- `devices`
- `device_bindings`
- `audit_logs`
- `alembic_version`

---

## 6. 演示数据

### 6.1 写入模拟数据

在仓库根目录执行：

```bash
./apps/seed-api-server.sh
```

或手动执行：

```bash
cd apps/api-server
source .venv/bin/activate
alembic upgrade head
python -m app.seed
```

### 6.2 模拟数据约定

当前种子数据均显式标记为模拟数据：

- 名称前缀：`[模拟数据]`
- 设备绑定前缀：`mock.`
- 审计动作：`seed.mock_data`

适用场景：

- 页面演示
- 前后端联调
- 非生产环境回归验证

---

## 7. 管理台启动

### 7.1 启动命令

在仓库根目录执行：

```bash
./apps/start-admin-web.sh
```

脚本会自动完成：

- 检测 `node` 与 `npm`
- 对 `package.json` 变化做依赖检查
- 自动 `npm install`
- 启动 Vite 热更新开发服务器

默认地址：

- `http://0.0.0.0:5173`

### 7.2 当前页面范围

当前管理台已可访问：

- 家庭管理
- 成员管理
- 成员关系
- 偏好与权限
- 房间与设备
- 审计日志

---

## 8. Home Assistant 联调

### 8.1 前提

需要准备：

- 可访问的 Home Assistant 地址
- 长期访问 Token

在 `apps/api-server/.env` 中配置：

```env
FAMILYCLAW_HOME_ASSISTANT_BASE_URL=http://your-ha-host:8123
FAMILYCLAW_HOME_ASSISTANT_TOKEN=your-long-lived-access-token
```

### 8.2 联调步骤

1. 启动后端：`./apps/start-api-server.sh`
2. 启动前端：`./apps/start-admin-web.sh`
3. 确保已存在当前家庭
4. 进入管理台“房间与设备”页
5. 点击“手动同步 HA 设备”
6. 观察设备列表与同步摘要
7. 进入“审计日志”页确认是否生成同步记录

### 8.3 接口联调方式

也可直接调用接口：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/devices/sync/ha" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "household_id": "YOUR_HOUSEHOLD_ID"
  }'
```

### 8.4 常见问题

#### HA 地址不可达

现象：

- 返回 `502`
- 错误信息通常为连接超时、连接被拒绝或路由不可达

排查建议：

- 确认主机与 HA 在同一网段
- 检查防火墙与端口 `8123`
- 确认 HA 已启动

#### Token 无效

现象：

- HA 同步失败
- 审计中记录失败结果

排查建议：

- 重新生成长期访问 Token
- 检查 `.env` 中是否有多余空格或换行

#### 同步后设备为空

排查建议：

- 检查 HA 中是否已有可识别实体
- 当前归一化面向常见家庭设备实体，非目标实体可能被跳过

---

## 9. 联调推荐顺序

建议按以下顺序验证：

1. 健康检查：`/api/v1/healthz`
2. 家庭创建与查询
3. 成员创建、编辑、停用
4. 成员关系配置
5. 成员偏好与权限配置
6. 房间创建与设备归属调整
7. HA 手动同步
8. 审计日志核对

---

## 10. 本轮联调验收建议

可按以下最小闭环进行：

1. 创建一个家庭
2. 创建至少 2 个成员
3. 配置 1 条成员关系
4. 为某成员保存偏好与权限
5. 创建 1 个房间
6. 触发 1 次 HA 同步
7. 调整至少 1 个设备归属
8. 在审计日志中确认关键写操作已记录

完成以上步骤，可视为当前 `家庭底座与成员中心` MVP 已具备首轮联调基础。
