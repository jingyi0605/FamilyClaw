# 任务清单 - 插件来源模型降级与安装方式收口（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只做一件事：把“砍掉 official、收口到 builtin/third_party + marketplace/local”这件事拆成可以执行、可以验收、不会越改越乱的步骤。

这次不能再搞“先改几个 if 试试看”。这个问题已经穿透到数据模型、目录结构、市场源、启动同步和文档，必须按阶段收口。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每完成一个任务，就要立刻回写这份文档

---

## 阶段 1：先把模型和目录口径收死

- [ ] 1.1 收口插件来源枚举和安装方式模型
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把插件系统里的 `official` 来源类型删出正式模型，只保留 `builtin` 和 `third_party`，并给第三方插件补上 `install_method`。
  - 做完你能看到什么：看插件挂载、安装结果和相关 schema 时，只会看到“内置还是第三方、市场装还是本地装”。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` 2.1《新的分类模型》
    - `design.md` 3.2《数据结构》
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/models.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - 相关 API / DTO / 校验逻辑
  - 这一步先不做什么：先不动磁盘迁移脚本和市场源表结构。
  - 怎么算完成：
    1. 正式枚举里不再定义 `official`
    2. 第三方插件相关读写接口显式带 `install_method`
    3. 内置插件不受第三方安装方式约束
  - 怎么验证：
    - 运行插件 schema 和 service 相关单元测试
    - 人工检查新旧字段是否还有并行正式写入口
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` 2.1、3.2.1、3.2.2、3.2.3、6.1

- [ ] 1.2 定死新的运行时目录和开发源码目录
  - 状态：TODO
  - 这一步到底做什么：把第三方插件开发源码目录从 `data/plugins` 挪出去，同时把运行时目录收口到 `third_party/local` 和 `third_party/marketplace`。
  - 做完你能看到什么：开发源码目录和运行时安装目录各干各的，不会互相覆盖。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` 2.2《目录结构》
    - `design.md` 6.2《开发源码目录不是运行时目录》
  - 主要改哪里：
    - `apps/api-server/app/core/config.py`
    - `apps/api-server/app/__init__.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/storage_cleanup.py`
    - 相关目录说明文档
  - 这一步先不做什么：先不处理旧目录回填，只把新路径和新配置口径定死。
  - 怎么算完成：
    1. 运行时目录生成函数只会生成新目录
    2. 宿主启动不再依赖 `data/plugins/official`
    3. 新开发规范明确第三方开发源码目录位置
  - 怎么验证：
    - 人工检查路径生成结果
    - 目录结构单元测试
    - 启动导入 smoke test
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` 2.2、2.4.1、2.4.2、6.2

### 阶段检查

- [ ] 1.3 模型和目录阶段检查
  - 状态：TODO
  - 这一步到底做什么：确认“正式模型”和“正式目录”已经说清楚，不再留一套新名字、一套旧实现。
  - 做完你能看到什么：后续做数据库迁移和启动同步时，不需要再猜模型到底是什么。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段涉及的所有后端代码和文档
  - 这一步先不做什么：不开始回填旧数据
  - 怎么算完成：
    1. 新模型和新目录在代码、文档里一致
    2. 已知兼容点和后续迁移点已经列清楚
  - 怎么验证：
    - 人工走查
    - 搜索 `official`、`trusted_level` 的剩余正式写路径
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` 2.1、2.2、6.1、6.2

---

## 阶段 2：迁数据库、迁目录、迁启动同步

- [ ] 2.1 迁移数据库字段和市场源模型
  - 状态：TODO
  - 这一步到底做什么：用 Alembic 把旧 `official` / `trusted_level` 数据模型迁到新模型，包括新增 `install_method`、收口旧来源值、给市场源改成 `is_system`。
  - 做完你能看到什么：数据库层不再靠 `official` 和 `trusted_level` 驱动核心逻辑。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4、需求 5
    - `design.md` 2.4.4《旧数据兼容与迁移流程》
    - `design.md` 3.2.3、3.2.4、3.2.5
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/plugin_marketplace/models.py`
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/modules/plugin/repository.py`
  - 这一步先不做什么：先不迁磁盘目录和启动同步扫描。
  - 怎么算完成：
    1. Alembic migration 能把旧字段迁到新字段
    2. 市场源正式模型不再依赖 `trusted_level`
    3. 新写入路径只会写新字段值
  - 怎么验证：
    - Alembic 升级 / 回滚测试
    - 迁移后数据库查询校验
    - 单元测试
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 5
  - 对应设计：`design.md` 2.4.4、3.2.3、3.2.4、3.2.5、6.3

- [ ] 2.2 迁移旧目录并重写启动同步
  - 状态：TODO
  - 这一步到底做什么：把旧 `official/marketplace` 目录迁到新目录，并把启动同步从“官方 / 手动 / 市场 trusted_level”三路改成“内置 / 本地 / 市场”三路。
  - 做完你能看到什么：宿主启动时不再扫描 `official`，第三方插件恢复逻辑只看安装方式。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` 2.4.3《启动同步流程》
    - `design.md` 2.4.4《旧数据兼容与迁移流程》
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/startup_sync_service.py`
    - `apps/api-server/app/modules/plugin/storage_cleanup.py`
    - 目录迁移脚本或一次性修复脚本
  - 这一步先不做什么：先不动前端展示和交互文案。
  - 怎么算完成：
    1. 启动同步只扫描新目录
    2. 旧市场安装目录能迁走或被兼容恢复
    3. 日志里能清楚看出安装方式
  - 怎么验证：
    - 启动同步集成测试
    - 旧目录迁移测试
    - 人工检查同步日志
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` 2.4.2、2.4.3、2.4.4、5.3

- [ ] 2.3 修正安装、升级、卸载和清理链路
  - 状态：TODO
  - 这一步到底做什么：把市场安装、本地安装、覆盖升级、卸载和清理逻辑全部改成按 `install_method` 工作。
  - 做完你能看到什么：删除市场安装不会误删本地安装，删除本地安装也不会去碰市场目录。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` 2.4.1、2.4.2
    - `design.md` 5.3《处理策略》
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/modules/plugin/storage_cleanup.py`
  - 这一步先不做什么：先不扩展新的安装入口类型。
  - 怎么算完成：
    1. 安装、升级、卸载全部按安装方式找路径
    2. 清理逻辑只删当前安装方式对应产物
    3. 不再通过 `trusted_level` 决定路径和行为
  - 怎么验证：
    - 本地安装 / 市场安装全链路测试
    - 卸载与清理回归测试
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` 2.4.1、2.4.2、3.3.1、5.1、5.3

### 阶段检查

- [ ] 2.4 迁移阶段检查
  - 状态：TODO
  - 这一步到底做什么：确认数据库、目录和启动同步已经全部切换到新口径，而不是“数据库改了，磁盘没改；磁盘改了，同步还走旧逻辑”。
  - 做完你能看到什么：系统内部已经没有新的 `official` 正式写入路径。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段涉及的迁移脚本、service 和测试
  - 这一步先不做什么：不开始整理最终文档和开发指南
  - 怎么算完成：
    1. 新安装和同步链路不再写旧值
    2. 旧目录和旧数据已有明确落点
    3. 兼容窗口和清理边界已经明确
  - 怎么验证：
    - 搜索剩余 `official` 正式写路径
    - 迁移回归测试
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4、需求 5
  - 对应设计：`design.md` 2.4.3、2.4.4、6.3

---

## 阶段 3：收文档、补测试、锁住后续口径

- [ ] 3.1 更新正式文档和开发规范
  - 状态：TODO
  - 这一步到底做什么：把插件目录、插件来源模型、市场源语义和第三方插件开发目录的正式文档全部更新掉。
  - 做完你能看到什么：后来者看文档不会再被“官方插件”这个旧概念带歪。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` 全文
    - 项目根 `AGENTS.md` 中的文档更新规则
  - 主要改哪里：
    - `docs/Documentation/`
    - `docs/开发者文档/`
    - `apps/api-server/data/marketplace/20260320-插件市场目录说明.md`
    - 受影响的插件开发说明文档
  - 这一步先不做什么：不再新增功能需求
  - 怎么算完成：
    1. 正式文档只讲新模型
    2. 开发规范明确开发源码目录和运行时目录分离
    3. 市场源文档不再使用 `trusted_level` 解释插件来源
  - 怎么验证：
    - 文档走查
    - 搜索正式文档中的 `official plugin`、`trusted_level`
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 1、2、3

- [ ] 3.2 补回归测试并删掉旧口径保护网
  - 状态：TODO
  - 这一步到底做什么：补齐单元、集成和端到端测试，把旧 `official` 口径的残留测试替换掉，并确认没有新的旧逻辑回流。
  - 做完你能看到什么：后面谁再把 `official` 加回去，测试会直接炸。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` 7《测试策略》
  - 主要改哪里：
    - `apps/api-server/tests/`
    - 相关后端模块测试和 fixture
  - 这一步先不做什么：不顺手扩展新的插件能力测试范围
  - 怎么算完成：
    1. 新模型关键链路有测试覆盖
    2. 旧 `official` 正式行为测试被替换为新模型测试
    3. 搜索和测试都能证明没有正式旧写路径
  - 怎么验证：
    - 单元测试
    - 集成测试
    - 端到端安装回归
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 5、6、7

### 最终检查

- [ ] 3.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这次收口真的完成了，而不是“代码改了一半，文档和迁移策略还挂着”。
  - 做完你能看到什么：任何接手的人都能直接看懂插件类型、安装方式、目录结构和迁移边界。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文档和相关正式文档
  - 这一步先不做什么：不再追加新范围
  - 怎么算完成：
    1. 需求、设计、任务、代码、测试、文档能一一对上
    2. 新模型已经成为唯一正式口径
    3. 旧 `official` 概念只保留在迁移说明或历史记录里
  - 怎么验证：
    - 按 Spec 清单逐项走查
    - 搜索仓库剩余旧口径
    - 核对迁移与回归测试结果
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
