# 需求文档 - PostgreSQL 数据库迁移收口

状态：DONE

## 简介

FamilyClaw 已经把生产环境和测试环境切到 PostgreSQL。现在真正要解决的问题，不是“能不能连 PostgreSQL”，而是把仓库口径彻底统一，避免还有人继续按 SQLite 双栈去理解和修改代码。

这份需求文档定义的就是迁移收口目标：运行时、测试、迁移、脚本和说明文档都只围绕 PostgreSQL 展开。

## 术语

- 主库：应用运行时使用的 PostgreSQL 数据库。
- 测试库：自动化测试使用的 PostgreSQL 数据库。
- 迁移链路：Alembic revision 与 `upgrade head` 执行流程。

## 范围说明

### In Scope

- 运行时代码只接受 PostgreSQL 连接。
- Alembic 迁移链路以 PostgreSQL 为唯一目标。
- 测试初始化流程统一使用 PostgreSQL。
- 删除或退役 SQLite 专用脚本。
- 更新 spec、开发文档和配置模板，避免继续误导为双栈。

### Out of Scope

- 生产数据库备份、高可用和监控方案。
- 线上不停机切换策略。
- 历史 SQLite 数据的再次导入需求。

## 需求

### 需求 1：运行时数据库统一

作为后端维护者，我希望应用只接受 PostgreSQL 连接，这样后续不会再因为“临时兼容 SQLite”留下隐藏分支。

#### 验收标准

1. WHEN 应用启动时读取数据库配置 THEN System SHALL 只接受 PostgreSQL URL。
2. WHEN 创建 engine 和 Session THEN System SHALL 使用 PostgreSQL 连接池参数，而不是保留 SQLite 专用分支。
3. WHEN 开发者误传 SQLite URL THEN System SHALL 明确报错，而不是继续运行。

### 需求 2：迁移链路统一

作为数据库维护者，我希望 Alembic 迁移只围绕 PostgreSQL 工作，这样 schema 语义和真实运行环境一致。

#### 验收标准

1. WHEN 对 PostgreSQL 空库执行 `alembic upgrade head` THEN System SHALL 成功建出完整 schema。
2. WHEN 模型里存在部分唯一索引等 PostgreSQL 语义 THEN System SHALL 通过模型和 migration 正确表达。
3. WHEN 查看迁移规范文档 THEN System SHALL 看到 PostgreSQL-only 的执行规则。

### 需求 3：测试基线统一

作为开发者，我希望测试从一开始就跑在 PostgreSQL 上，这样测试暴露的是现实问题，不是 SQLite 的宽松行为。

#### 验收标准

1. WHEN 测试初始化数据库 THEN System SHALL 使用 PostgreSQL 测试库和独立 schema。
2. WHEN 测试构造父子记录 THEN System SHALL 满足 PostgreSQL 的外键时序要求。
3. WHEN 运行关键数据库相关测试 THEN System SHALL 不再依赖 SQLite。

### 需求 4：仓库口径统一

作为后续接手的人，我希望仓库里的说明、模板和脚本说的是同一件事，这样不会被过时文档带偏。

#### 验收标准

1. WHEN 查看 `.env.example` THEN System SHALL 看到 PostgreSQL 模板。
2. WHEN 查看 spec 001.7 THEN System SHALL 看到 PostgreSQL-only 的需求、设计和任务状态。
3. WHEN 查看仍保留历史描述的旧文档 THEN System SHALL 明确标注那是历史信息，不是当前基线。

## 成功定义

- 运行时和测试都不再依赖 SQLite。
- 仓库主线不再保留 SQLite 导入脚本。
- 关键测试能在 PostgreSQL 上运行。
- 文档口径与当前实现一致。
