# 任务清单 - 插件配置协议与动态表单（人话版）

状态：Draft

## 这份任务清单是干什么的

这份清单不是用来堆术语的，是用来保证这次别再走回“先写页面，后补协议，再补存储”的老路。

这次顺序必须很死：

1. 先把协议定住
2. 再把后端持久化和接口补齐
3. 再把前端 renderer 接起来
4. 最后拿 `channel` 做第一批迁移

顺序反了，后面一定重新长出特例代码。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：确认不做，但必须写清原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，必须立刻回写这份文件
- 发现范围变了，不要偷偷加活，先改 Spec

---

## 阶段 1：先把协议定型

- [ ] 1.1 定义插件 manifest 配置协议
  - 状态：TODO
  - 这一阶段到底做什么：把插件配置描述收成正式结构，明确 `config_schema`、`ui_schema`、`scope_type` 和 `schema_version` 语义。
  - 做完你能看到什么：插件不再只能在代码里偷偷约定配置字段，而是能在 manifest 里正式声明。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.1
    - `design.md` §3.2.1
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/plugins/builtin/*/manifest.json`
    - `apps/api-server/app/modules/plugin/service.py`
  - 这一阶段先不做什么：先不碰数据库，不先写前端 renderer。
  - 怎么算完成：
    1. manifest 可以声明配置作用域和 schema 版本
    2. 插件加载时能校验不合法协议并报错
  - 怎么验证：
    - 代码走查
    - manifest 解析单测
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.1、§3.2.1

- [ ] 1.2 定义字段类型、UI widget 和 secret 语义
  - 状态：TODO
  - 这一阶段到底做什么：把第一版支持的字段类型、显示条件、secret 保留与清空语义全部定死。
  - 做完你能看到什么：后端和前端都知道哪些字段能用，哪些不能用，secret 怎么处理。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1
    - `requirements.md` 需求 4
    - `design.md` §3.2.2
    - `design.md` §3.2.3
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/user-web/src/lib/types.ts`
    - `apps/user-web/src/lib/api.ts`
  - 这一阶段先不做什么：先不实现完整 UI，只先把协议边界写死。
  - 怎么算完成：
    1. 字段类型集合和 widget 集合固定下来
    2. `clear_secret_fields` 语义在前后端契约里一致
  - 怎么验证：
    - 协议文档走查
    - 类型检查和接口契约走查
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` §3.2.2、§3.2.3、§3.3.3

### 阶段检查

- [ ] 1.3 协议定型检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认这次不是“看起来有 schema”，而是真的把配置协议边界讲清楚了。
  - 做完你能看到什么：后面做持久化和前端时，不需要再反过来改协议定义。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 文档和相关 schema 定义
  - 这一阶段先不做什么：不新增新的作用域，不补远程选项源。
  - 怎么算完成：
    1. 协议字段集合、scope 语义和 secret 语义都已写清楚
    2. 当前已知插件场景至少能映射进去，不需要再开特例
  - 怎么验证：
    - 文档走查
    - 用 `channel` 和普通插件各跑一遍设计映射
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 5
  - 对应设计：`design.md` §2、§3

---

## 阶段 2：补后端持久化与接口

- [ ] 2.1 新增插件配置实例模型和 migration
  - 状态：TODO
  - 这一阶段到底做什么：新增 `plugin_config_instances` 正式表，把配置实例放进数据库，不再散落在业务表或本地结构里。
  - 做完你能看到什么：后端已经有统一地方保存插件配置和 secret。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §3.2.4
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/models.py`
    - `apps/api-server/app/modules/plugin/repository.py`
    - `apps/api-server/migrations/versions/`
  - 这一阶段先不做什么：先不接前端，不处理页面交互。
  - 怎么算完成：
    1. 配置实例可以按 `household_id + plugin_id + scope_type + scope_key` 唯一保存
    2. secret 字段有独立加密存储位置，不走明文
  - 怎么验证：
    - Alembic migration 走查
    - repository 单测
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §3.2.4、§4.1

- [ ] 2.2 实现统一配置服务和读写 API
  - 状态：TODO
  - 这一阶段到底做什么：把 schema 解析、默认值合并、字段校验、secret 处理和配置读写接口接成一条链。
  - 做完你能看到什么：前端已经能通过正式 API 读取配置表单和保存配置。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` §2.3.1
    - `design.md` §2.3.2
    - `design.md` §3.3
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`
  - 这一阶段先不做什么：先不重做旧页面。
  - 怎么算完成：
    1. 可以读取插件可配置作用域列表
    2. 可以读取某个作用域的配置表单和当前值
    3. 可以保存配置并返回字段级错误
  - 怎么验证：
    - API 集成测试
    - 配置保存失败与 secret 保留语义测试
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.3

### 阶段检查

- [ ] 2.3 后端配置链路检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认后端不是“有接口但不能可靠存值”，而是真的能稳定读写配置。
  - 做完你能看到什么：后面接前端时，不需要再因为接口语义不清来回返工。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段涉及的后端模型、服务、接口和 migration
  - 这一阶段先不做什么：不做 `channel` 迁移，不补页面样式细节。
  - 怎么算完成：
    1. 读写接口语义固定
    2. 默认值、校验、secret 语义一致
  - 怎么验证：
    - 后端联调
    - 测试用例回放
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3、§3.2.4、§3.3

---

## 阶段 3：补前端动态表单 renderer

- [ ] 3.1 实现通用插件配置表单 renderer
  - 状态：TODO
  - 这一阶段到底做什么：把输入框、密码框、文本域、开关、下拉、多选和 JSON 编辑器这些基础控件接成一套通用 renderer。
  - 做完你能看到什么：前端不再需要按插件 id 写死字段表单。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §3.2.2
    - `design.md` §3.2.3
  - 主要改哪里：
    - `apps/user-web/src/components/plugin-config/DynamicPluginConfigForm.tsx`
    - `apps/user-web/src/components/plugin-config/fields/*`
    - `apps/user-web/src/lib/types.ts`
  - 这一阶段先不做什么：先不做复杂低代码布局，不做远程选项源。
  - 怎么算完成：
    1. 第一版字段类型都能被渲染
    2. 字段错误、帮助说明和 secret 状态能正确展示
  - 怎么验证：
    - 组件测试
    - 手工走查表单渲染结果
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §3.2.2、§3.2.3、§3.2.5

- [ ] 3.2 接入插件详情和通用配置入口
  - 状态：TODO
  - 这一阶段到底做什么：把插件详情抽屉和配置入口改成消费新接口和新 renderer。
  - 做完你能看到什么：用户已经能在插件管理界面里看到统一的配置入口和保存反馈。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3
    - `requirements.md` 需求 5
    - `design.md` §2.3.1
    - `design.md` §3.3.1
    - `design.md` §3.3.2
  - 主要改哪里：
    - `apps/user-web/src/components/PluginDetailDrawer.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 这一阶段先不做什么：先不迁移 `channel` 页面里的专用表单。
  - 怎么算完成：
    1. 插件详情可以识别插件是否有配置作用域
    2. 插件详情可以打开并保存 `plugin` 作用域配置
  - 怎么验证：
    - 前端联调
    - 手工验证保存成功与错误提示
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` §2.3.1、§3.3.1、§3.3.2

### 阶段检查

- [ ] 3.3 动态表单检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认前端已经真的摆脱“按插件写死字段”的旧模式。
  - 做完你能看到什么：新增一个有配置协议的插件时，不需要再先改一遍前端字段常量。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段涉及的 renderer、API 适配和插件详情页
  - 这一阶段先不做什么：不扩展新控件类型，不引入视觉重构。
  - 怎么算完成：
    1. 表单渲染完全由协议驱动
    2. secret、错误和默认值展示可用
  - 怎么验证：
    - 手工联调
    - 前端测试回放
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §2.3.1、§3.2.5、§6.1

---

## 阶段 4：首批迁移 `channel`

- [ ] 4.1 给通道插件补正式配置协议
  - 状态：TODO
  - 这一阶段到底做什么：把 `channel_telegram` 等通道插件需要的字段从页面常量搬回 manifest。
  - 做完你能看到什么：通道插件自己的字段定义终于回到插件本身，而不是散落在前端页面里。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §2.3.3
    - `design.md` §3.2.1
    - `design.md` §4.1
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/channel_telegram/manifest.json`
    - `apps/api-server/app/plugins/builtin/channel_discord/manifest.json`
    - `apps/api-server/app/plugins/builtin/channel_feishu/manifest.json`
    - 其他首批通道插件 manifest
  - 这一阶段先不做什么：先不要求所有插件都迁完。
  - 怎么算完成：
    1. 首批通道插件都能从 manifest 读出配置字段
    2. 不再依赖前端页面常量定义这些字段
  - 怎么验证：
    - manifest 走查
    - schema 解析测试
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` §2.3.3、§3.2.1

- [ ] 4.2 把通道配置页改成通用 renderer 驱动
  - 状态：TODO
  - 这一阶段到底做什么：让 `SettingsChannelAccessPage` 从写死字段切到统一协议与 `channel_account` 作用域。
  - 做完你能看到什么：通道账号配置页不再维护 `PLATFORM_CONFIG_FIELDS` 这类特例常量。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 3
    - `requirements.md` 需求 5
    - `design.md` §2.3.3
    - `design.md` §3.3.2
  - 主要改哪里：
    - `apps/user-web/src/pages/SettingsChannelAccessPage.tsx`
    - `apps/user-web/src/components/plugin-config/DynamicPluginConfigForm.tsx`
    - `apps/api-server/app/modules/channel/*`
  - 这一阶段先不做什么：先不重做整页信息架构，只替换字段来源和保存链路。
  - 怎么算完成：
    1. 通道账号配置页按协议渲染字段
    2. 保存后仍能继续执行当前通道探测和绑定流程
  - 怎么验证：
    - 通道配置联调
    - 人工回归通道创建、编辑、probe
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` §2.3.3、§3.3.2、§6.4

### 阶段检查

- [ ] 4.3 `channel` 迁移检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认 `channel` 已经真正接入统一协议，而不是旧页面套一个新壳。
  - 做完你能看到什么：首批最复杂的配置场景已经被这套协议吃下来了。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段涉及的通道插件 manifest、页面和后端适配
  - 这一阶段先不做什么：不扩展第二批插件迁移。
  - 怎么算完成：
    1. 通道插件字段定义只保留一份来源
    2. 通道页面保存链路已切到统一配置实例
  - 怎么验证：
    - 联调回归
    - 代码走查确认删除旧字段常量
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` §2.3.3、§4.1、§6.4

---

## 阶段 5：测试、文档和收口

- [ ] 5.1 补测试和示例
  - 状态：TODO
  - 这一阶段到底做什么：补齐后端单测、接口测试、前端组件测试和至少一份 manifest 示例。
  - 做完你能看到什么：这套协议不是只靠肉眼看起来对，而是有回归保护。
  - 先依赖什么：4.3
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` §7
    - `docs/README.md`
  - 主要改哪里：
    - `apps/api-server/tests/`
    - `apps/user-web/src/components/plugin-config/__tests__/`
    - `specs/004.2.3-插件配置协议与动态表单/docs/`
  - 这一阶段先不做什么：不额外扩需求，不顺手做设计器。
  - 怎么算完成：
    1. 核心字段类型、secret 语义和 `channel` 迁移都有测试覆盖
    2. 至少有一份插件 manifest 示例能给后续开发者照着抄
  - 怎么验证：
    - 测试执行
    - 文档走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §7

- [ ] 5.2 补迁移说明和联调清单
  - 状态：TODO
  - 这一阶段到底做什么：把后续插件怎么接入、旧页面怎么迁、联调看什么写成接手文档。
  - 做完你能看到什么：后来的人不需要重新猜这套协议怎么用。
  - 先依赖什么：5.1
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `docs/README.md`
  - 主要改哪里：
    - `specs/004.2.3-插件配置协议与动态表单/docs/README.md`
    - `specs/004.2.3-插件配置协议与动态表单/docs/api-示例.md`
    - `specs/004.2.3-插件配置协议与动态表单/docs/channel-迁移说明.md`
  - 这一阶段先不做什么：不写一堆空洞说明，文档只写接手时真会看的内容。
  - 怎么算完成：
    1. 新插件接入步骤写清楚
    2. `channel` 迁移边界和回归点写清楚
  - 怎么验证：
    - 文档走查
  - 对应需求：`requirements.md` 需求 5、非功能需求 3
  - 对应设计：`design.md` §4.1、§7、§8

### 最终检查

- [ ] 5.3 最终检查点
  - 状态：TODO
  - 这一阶段到底做什么：确认这次真的把“通用插件配置协议 + 动态表单渲染 + 配置持久化”讲成了一套完整方案。
  - 做完你能看到什么：后续实现时，团队不会再因为边界不清重新争论数据结构。
  - 先依赖什么：5.1、5.2
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部内容
  - 这一阶段先不做什么：不再新增需求，不再顺手扩 scope。
  - 怎么算完成：
    1. 需求、设计、任务互相能对上
    2. 协议、存储、渲染、迁移四块都讲清楚
    3. 后续实现知道先做什么、别做什么
  - 怎么验证：
    - 按 Spec 逐项走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
