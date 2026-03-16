# Spec 001.7 - PostgreSQL 数据库迁移

状态：DONE

## 这份 Spec 现在解决什么

这份 Spec 不再讨论“要不要从 SQLite 迁到 PostgreSQL”。这件事已经做完了。

它现在记录的是：

1. FamilyClaw 的运行时数据库基线已经统一为 PostgreSQL。
2. 测试基线也已经统一为 PostgreSQL。
3. 仓库里与 SQLite 相关的运行时代码、测试路径和误导性说明已经被收口或退役。

## 当前结论

- 主库只支持 PostgreSQL。
- 测试只支持 PostgreSQL。
- Alembic 迁移链路以 PostgreSQL 为准。
- 旧的 SQLite 导入脚本不再保留在仓库主线。

## 接手时先看哪里

1. `tasks.md`
2. `requirements.md`
3. `design.md`
4. `docs/README.md`
