# 设计文档 - PostgreSQL 数据库迁移收口

状态：DONE

## 1. 设计目标

这次设计不追求“同时兼容两套数据库”。那种方案只会把复杂度重新带回来。

目标很简单：

1. 运行时只认 PostgreSQL。
2. 测试只认 PostgreSQL。
3. Alembic、模型、测试基建和文档口径一致。

## 2. 核心判断

### 2.1 数据结构

- 应用运行时只需要一条数据库主链路：`Settings -> engine -> SessionLocal -> Alembic`。
- 测试只需要一套隔离手段：同一个 PostgreSQL 实例下按测试创建独立 schema。
- 过去的 SQLite 分支不是新的能力，只是历史包袱。

### 2.2 复杂度收口

要删除的复杂度：

- SQLite/ PostgreSQL 双分支 engine 构建。
- SQLite 专用 pragma 和连接参数判断。
- “运行时 PostgreSQL、测试暂时 SQLite” 这种半切换状态。
- 已经失效的 SQLite 导入脚本和误导性文档。

## 3. 方案

### 3.1 运行时入口

- `app/core/config.py` 提供 PostgreSQL URL 和连接池参数。
- `app/db/engine.py` 统一校验数据库 URL，非 PostgreSQL 直接报错。
- `app/db/session.py` 只基于 PostgreSQL engine 构造 `SessionLocal`。

### 3.2 迁移链路

- `migrations/env.py` 直接接受外部传入的连接或 URL。
- Alembic 在线迁移直接使用 PostgreSQL engine，不再维护 SQLite 特殊逻辑。
- 模型中的部分索引只保留 `postgresql_where`。

### 3.3 测试基建

- `tests/test_db_support.py` 负责：
  - 读取 `FAMILYCLAW_TEST_DATABASE_URL`
  - 为每个测试创建独立 schema
  - 执行 `alembic upgrade head`
  - 在测试结束后 `DROP SCHEMA ... CASCADE`
- 测试构造父子表数据时，在 PostgreSQL 需要父记录先 `flush()` 再插入子记录。

### 3.4 文档与脚本

- `.env.example` 只保留 PostgreSQL 模板。
- 退役 SQLite 导入脚本，不再把它当主线能力维护。
- Spec 001.7 重写为 PostgreSQL-only 口径。
- 历史文档若仍保留旧描述，顶部必须明确标注“仅供历史参考”。

## 4. 关键文件

| 文件 | 作用 |
| --- | --- |
| `apps/api-server/app/db/engine.py` | PostgreSQL-only engine 构建 |
| `apps/api-server/app/db/session.py` | Session 入口 |
| `apps/api-server/migrations/env.py` | Alembic 迁移入口 |
| `apps/api-server/tests/test_db_support.py` | PostgreSQL 测试基建 |
| `apps/api-server/tests/test_db_engine.py` | 数据库入口和索引语义验证 |
| `specs/001.7-PostgreSQL数据库迁移/*` | 当前迁移收口说明 |

## 5. 风险与处理

### 风险 1：测试仍按 SQLite 的宽松行为写

处理：

- 优先修测试，不为迁就错误测试去放宽业务代码。
- 父子记录插入顺序问题通过 `flush()` 显式解决。

### 风险 2：旧文档继续误导

处理：

- 当前 spec 和规范文档全部改成 PostgreSQL-only。
- 历史文档保留时必须显式加历史说明。

### 风险 3：有人继续引入 SQLite 分支

处理：

- engine 层直接拒绝 SQLite URL。
- 测试辅助设施只接受 PostgreSQL URL。

## 6. 验证策略

1. 扫描仓库，确认运行时代码和测试代码不再依赖 SQLite。
2. 运行关键数据库测试，确认 PostgreSQL 测试基建和外键时序正确。
3. 检查 spec、迁移规范和配置模板，确认口径一致。
