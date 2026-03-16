# 任务清单 - PostgreSQL 数据库迁移收口

状态：DONE

## 这份任务清单在做什么

它记录的是从“已经能连 PostgreSQL”到“仓库彻底按 PostgreSQL-only 运行”的收口过程。

---

## 阶段 1：统一运行时入口

- [x] 1.1 把数据库配置模板改成 PostgreSQL
  - 做什么：把 `.env.example` 改成 PostgreSQL 模板，并补齐测试库连接变量。
  - 做完能看到什么：开发者打开模板时不会再看到 SQLite 作为默认选项。
  - 依赖什么：无。
  - 主要改哪些文件：
    - `apps/api-server/.env.example`
    - `apps/api-server/app/core/config.py`
  - 明确不做什么：不讨论生产备份、高可用。
  - 怎么验证：人工检查模板和配置字段。

- [x] 1.2 把 engine 和 Session 收口成 PostgreSQL-only
  - 做什么：删除 SQLite 分支，只保留 PostgreSQL engine 构建。
  - 做完能看到什么：运行时误传 SQLite URL 会直接报错。
  - 依赖什么：1.1。
  - 主要改哪些文件：
    - `apps/api-server/app/db/engine.py`
    - `apps/api-server/app/db/session.py`
  - 明确不做什么：不保留双栈兼容。
  - 怎么验证：运行 `tests.test_db_engine`。

---

## 阶段 2：统一迁移链路

- [x] 2.1 修正模型和 migration 中的 PostgreSQL 语义
  - 做什么：清理模型和 migration 中依赖 SQLite 的条件分支，保留 PostgreSQL 正确语义。
  - 做完能看到什么：部分唯一索引等约束在 PostgreSQL 下表达正确。
  - 依赖什么：1.2。
  - 主要改哪些文件：
    - `apps/api-server/app/modules/agent/models.py`
    - `apps/api-server/app/modules/ai_gateway/models.py`
    - `apps/api-server/migrations/versions/*.py`
  - 明确不做什么：不修改业务语义。
  - 怎么验证：Alembic 升级和索引相关单元测试。

- [x] 2.2 把 Alembic 入口改成 PostgreSQL 主链路
  - 做什么：让 `migrations/env.py` 直接接受 PostgreSQL 连接或 URL，不再维护 SQLite 特判。
  - 做完能看到什么：测试和脚本都能稳定把 migration 跑到 `head`。
  - 依赖什么：2.1。
  - 主要改哪些文件：
    - `apps/api-server/migrations/env.py`
    - `apps/start-api-server.sh`
  - 明确不做什么：不在业务代码里自动补表。
  - 怎么验证：PostgreSQL 测试 schema 初始化。

---

## 阶段 3：统一测试基线

- [x] 3.1 建立 PostgreSQL 测试辅助设施
  - 做什么：为每个测试分配独立 schema，并在 schema 内跑 Alembic。
  - 做完能看到什么：测试不再依赖 SQLite 临时库。
  - 依赖什么：2.2。
  - 主要改哪些文件：
    - `apps/api-server/tests/test_db_support.py`
    - `apps/api-server/tests/test_*.py`
  - 明确不做什么：不共享脏测试库。
  - 怎么验证：关键测试可以在 PostgreSQL 下启动并清理。

- [x] 3.2 修正 PostgreSQL 下暴露的测试数据时序问题
  - 做什么：在父记录写入后补 `flush()`，再写子记录。
  - 做完能看到什么：外键测试失败从“数据库时序问题”变回真实业务问题。
  - 依赖什么：3.1。
  - 主要改哪些文件：
    - `apps/api-server/tests/test_conversation_proposal_repository.py`
    - `apps/api-server/tests/test_realtime_ws.py`
    - `apps/api-server/tests/test_bootstrap_storage.py`
  - 明确不做什么：不为了迁就错误测试去放宽业务约束。
  - 怎么验证：定向 `unittest`。

---

## 阶段 4：清理 SQLite 尾巴

- [x] 4.1 删除废弃的 SQLite 导入脚本
  - 做什么：移除已经不再维护的 SQLite 导入脚本，避免仓库继续假装支持旧链路。
  - 做完能看到什么：主线仓库不再保留失效的 SQLite 导入入口。
  - 依赖什么：3.2。
  - 主要改哪些文件：
    - `apps/api-server/scripts/migrate_sqlite_to_postgresql.py`
  - 明确不做什么：不保留半废弃脚本。
  - 怎么验证：仓库扫描不再出现该脚本引用。

- [x] 4.2 更新 spec 和开发文档口径
  - 做什么：把 spec 001.7 和数据库迁移规范改写为 PostgreSQL-only，并给历史文档加清晰说明。
  - 做完能看到什么：后续接手的人不会再被双栈表述误导。
  - 依赖什么：4.1。
  - 主要改哪些文件：
    - `specs/001.7-PostgreSQL数据库迁移/*`
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
    - 历史文档中的相关说明
  - 明确不做什么：不重写所有历史设计，只做必要收口和说明。
  - 怎么验证：人工检查和仓库关键字扫描。
