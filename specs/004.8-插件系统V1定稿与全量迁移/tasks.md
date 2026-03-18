# 任务清单 - 插件系统 V1 定稿与全量迁移（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只做一件事：把这次大重构拆成可以执行、可以验收、可以回写状态的步骤。

这次不接受“先改一点看看”“顺手再补几个能力”这种散打。插件系统已经踩到架构边界了，必须按阶段硬收口。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

---

## 阶段 1：先把规范和开发者手册收口

- [ ] 1.1 重构插件规范文档与开发者手册目录
  - 状态：IN_PROGRESS
  - 这一步到底做什么：按“少改动的固定规则 + 高频变化的接口表与调用方式”重构插件相关 Spec、开发设计规范和开发者文档目录。
  - 做完你能看到什么：插件开发者手册有统一入口，稳定规则和接口事实不再混写。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.3.1「插件文档收口流程」
    - `design.md` §3.3.1「插件文档索引契约」
    - `C:\Code\FamilyClaw\docs\开发设计规范\20260318-插件能力与接口规范-v1.md`
    - `C:\Code\FamilyClaw\docs\开发设计规范\20260318-记忆中心内核与插件边界规范.md`
  - 主要改哪里：
    - `C:\Code\FamilyClaw\docs\开发设计规范\*.md`
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\README.md`
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\zh-CN\*.md`
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\en\*.md`
    - `C:\Code\FamilyClaw\specs\004.3-插件开发规范与注册表\*`
    - `C:\Code\FamilyClaw\specs\004.5-插件能力统一接入与版本治理\*`
  - 这一步先不做什么：先不改宿主运行时代码。
  - 怎么算完成：
    1. 有稳定规则总入口
    2. 有接口表和调用方式事实来源页
    3. 旧文档中重复、冲突、明显过时的章节已收口或重定向
  - 怎么验证：
    - 人工走查文档目录与引用关系
    - 核对命名是否统一为 V1 正式类型与槽位名
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.3.1、§3.1、§3.3

- [ ] 1.2 写清正式类型、标准 DTO 与槽位接口表
  - 状态：TODO
  - 这一步到底做什么：把插件类型、配置作用域、标准 DTO、`integration.refresh`、记忆槽位契约整理成后续直接可对照开发的接口表。
  - 做完你能看到什么：后续改代码时，不需要再到处猜字段、猜命名、猜入口。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §3.2「数据结构」
    - `design.md` §3.3「接口契约」
  - 主要改哪里：
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\zh-CN\03-manifest字段规范.md`
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\zh-CN\05-插件对接方式说明.md`
    - `C:\Code\FamilyClaw\docs\开发者文档\插件开发\zh-CN\11-插件配置接入说明.md`
    - 对应英文文档
    - 必要的补充接口表文档
  - 这一步先不做什么：先不迁内置插件。
  - 怎么算完成：
    1. V1 正式类型和槽位名有一份唯一接口表
    2. DTO 和调用方式可直接指导代码实现
  - 怎么验证：
    - 人工核对接口表与规范文档命名一致
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §3.2、§3.3、§6.2

### 阶段检查

- [ ] 1.3 文档阶段检查
  - 状态：TODO
  - 这一步到底做什么：检查文档是不是已经能当正式手册用，而不是继续堆草稿。
  - 做完你能看到什么：后面改核心代码时有稳定参照，不会边改边猜。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部文档
  - 这一步先不做什么：不继续加新能力范围。
  - 怎么算完成：
    1. 文档结构稳定
    2. 命名一致
    3. 事实来源明确
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.3.1、§6.2

---

## 阶段 2：重构宿主插件核心

- [ ] 2.1 收口插件类型体系、manifest 校验和生命周期
  - 状态：TODO
  - 这一步到底做什么：把宿主插件核心里的旧类型语义收掉，改成 V1 正式类型和生命周期。
  - 做完你能看到什么：宿主不再把 `connector`、`memory-ingestor` 当主设计语义。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.2「普通插件运行流程」
    - `design.md` §3.2.1「PluginManifestV1」
  - 主要改哪里：
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\plugin\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\integration\*`
    - 相关 schema、service、runtime、registry 文件
  - 这一步先不做什么：先不迁具体内置插件逻辑。
  - 怎么算完成：
    1. 宿主正式识别 V1 类型体系
    2. 旧主语义从主流程中移除
  - 怎么验证：
    - 单元测试
    - manifest 加载与校验人工走查
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.2、§3.2.1、§5.3

- [ ] 2.2 建立统一 `integration` 标准 DTO 与刷新主链路
  - 状态：TODO
  - 这一步到底做什么：把实例、设备、实体、动作、卡片快照的标准输出和宿主落库逻辑统一起来。
  - 做完你能看到什么：状态型插件都能走同一条正式主链路。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §3.2.2「IntegrationRefreshResult」
    - `design.md` §4.1「数据关系」
  - 主要改哪里：
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\device\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\device_integration\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\integration\*`
    - 相关 API、schema、service、worker 文件
  - 这一步先不做什么：先不处理记忆槽位。
  - 怎么算完成：
    1. 有统一刷新返回结构
    2. 宿主能按统一 DTO 校验、去重、落库、更新状态
  - 怎么验证：
    - 单元测试
    - 集成测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.2、§3.2.2、§4.1

- [ ] 2.3 建立记忆槽位型插件运行时与宿主边界
  - 状态：TODO
  - 这一步到底做什么：把记忆相关插件接入收口到 `memory_engine`、`memory_provider`、`context_engine` 三个槽位，并把宿主主权边界钉死。
  - 做完你能看到什么：记忆相关扩展不再走野路子，宿主也不会把主权让出去。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.3「槽位型插件运行流程」
    - `design.md` §3.2.3「SlotContractDescriptor」
    - `C:\Code\FamilyClaw\docs\开发设计规范\20260318-记忆中心内核与插件边界规范.md`
  - 主要改哪里：
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\memory\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\context\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\modules\plugin\*`
  - 这一步先不做什么：先不引入新的第三方记忆后端。
  - 怎么算完成：
    1. 槽位名、契约和 fallback 策略统一
    2. 宿主保留权限、可见性、修订和审计
  - 怎么验证：
    - 单元测试
    - 插槽 fallback 走查
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.3、§3.2.3、§6.1

### 阶段检查

- [ ] 2.4 宿主核心阶段检查
  - 状态：TODO
  - 这一步到底做什么：确认宿主核心已经按 V1 收口，而不是换了几个名字、旧分支还在。
  - 做完你能看到什么：后面迁插件时不会再被旧主流程拖住。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部核心代码
  - 这一步先不做什么：不开始补新业务字段。
  - 怎么算完成：
    1. 宿主主流程只认 V1 正式语义
    2. 旧主语义已从关键链路移除
  - 怎么验证：
    - 集成测试
    - 代码走查
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2、§3、§6

---

## 阶段 3：全量迁移内置插件与官方插件

- [ ] 3.1 迁移状态型与控制型内置插件
  - 状态：TODO
  - 这一步到底做什么：把 `official-weather`、`health-basic`、`homeassistant_*`、`open_xiaoai_speaker` 等插件改到正式类型和正式入口。
  - 做完你能看到什么：这些插件不会再各写各的主链路。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §3.1「核心组件」
    - `design.md` §4.1「数据关系」
  - 主要改哪里：
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\official_weather\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\health_basic\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\homeassistant_*\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\open_xiaoai_speaker\*`
  - 这一步先不做什么：先不新增任何业务字段。
  - 怎么算完成：
    1. manifest、入口和输出都改成 V1
    2. 旧 `connector` / `memory-ingestor` 主语义不再出现
  - 怎么验证：
    - 插件回归测试
    - manifest 人工检查
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §2.3.2、§4.1、§5.3

- [ ] 3.2 迁移通道插件与资源包插件
  - 状态：TODO
  - 这一步到底做什么：把 `channel-*` 与 `locale-zh-tw` 等插件的 manifest、权限声明和文档收口到新规范。
  - 做完你能看到什么：所有内置插件都至少在类型语义和规范层一致。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §3.2.1「PluginManifestV1」
    - `design.md` §6.2「同一能力只有一套正式语义」
  - 主要改哪里：
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\channel_*\*`
    - `C:\Code\FamilyClaw\apps\api-server\app\plugins\builtin\locale_zh_tw_pack\*`
  - 这一步先不做什么：先不扩市场展示能力。
  - 怎么算完成：
    1. 通道插件和资源包插件符合 V1 manifest 规则
    2. 没有继续保留旧命名和旧字段混用
  - 怎么验证：
    - manifest 校验
    - 文档走查
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §3.2.1、§6.2

- [ ] 3.3 清理旧分支、补测试并做最终验收
  - 状态：TODO
  - 这一步到底做什么：删掉明确过时的旧主语义，补回归测试，形成最终迁移结果。
  - 做完你能看到什么：仓库里只剩一套正式插件系统架构，而不是新旧并存。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：
    - 插件核心相关测试
    - 内置插件相关测试
    - 明确过时的旧实现分支和无效文档
  - 这一步先不做什么：不再追加新业务。
  - 怎么算完成：
    1. 关键回归测试覆盖到新主链路
    2. 旧主语义和明显过时分支被删除或封口
    3. 文档、代码、插件实现三者一致
  - 怎么验证：
    - 单元测试
    - 集成测试
    - 最终人工验收
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
