# 20260316-PostgreSQL切换与收口说明

## 当前基线

- `FAMILYCLAW_DATABASE_URL` 必须是 PostgreSQL。
- `FAMILYCLAW_TEST_DATABASE_URL` 也必须是 PostgreSQL。
- 运行时、Alembic 和测试都不再以 SQLite 为基线。

## 配置方式

在 `apps/api-server/.env` 中至少配置：

```env
FAMILYCLAW_DATABASE_URL=postgresql+psycopg://familyclaw:change-me@127.0.0.1:5432/familyclaw
FAMILYCLAW_TEST_DATABASE_URL=postgresql+psycopg://familyclaw_test:change-me@127.0.0.1:5432/familyclaw_test
FAMILYCLAW_DB_POOL_SIZE=10
FAMILYCLAW_DB_MAX_OVERFLOW=20
FAMILYCLAW_DB_POOL_TIMEOUT_SECONDS=30
FAMILYCLAW_DB_POOL_RECYCLE_SECONDS=1800
```

## 建库方式

项目只认 Alembic：

```bash
cd apps/api-server
alembic upgrade head
```

不要再用 `create_all()` 之类的旁门左道。

## 测试方式

测试会读取 `FAMILYCLAW_TEST_DATABASE_URL`，并为每个测试创建独立 schema。

这意味着：

- 测试可以并行隔离。
- PostgreSQL 外键和约束会真实生效。
- 不会再出现“SQLite 能过，生产会炸”的假绿灯。

## 已退役内容

- SQLite 运行时支持
- SQLite 测试基线
- SQLite 导入脚本

如果以后还需要做一次性历史数据整理，应该另开专用脚本或专用仓库，不要把临时迁移工具继续挂在主线里。
