# 20260316-PostgreSQL迁移验收记录

## 验收结论

本次迁移收口的结论是：FamilyClaw 仓库主线已经按 PostgreSQL-only 组织，SQLite 不再作为运行时或测试基线存在。

## 本轮确认的结果

1. 运行时 engine 与 Session 入口只接受 PostgreSQL。
2. Alembic 迁移入口按 PostgreSQL 链路工作。
3. 测试基础设施使用 PostgreSQL 测试库和独立 schema。
4. 已知的父子记录插入顺序问题已经按 PostgreSQL 约束修正。
5. 旧的 SQLite 导入脚本已从主线移除。

## 还保留的历史信息

- 部分旧 spec 文档仍会提到 SQLite。
- 这些内容只作为历史背景保留，文档顶部已加说明，不能再当成当前实现依据。

## 后续约束

1. 新增数据库相关代码时，不要重新引入 SQLite 分支。
2. 新测试默认走 PostgreSQL 测试辅助设施。
3. 表结构变更继续只通过 Alembic 交付。
