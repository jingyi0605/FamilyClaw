# 任务清单 - 设备与集成全插件化重构（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来摆姿态的，是拿来保证这次改造真的能落地，而且不会又变成“后端改了一半，页面还在写死 HA”。

这次任务的判断标准只有一个：

- 最终用户在“设备与集成”页看到的是统一插件管理，不是 HA 页面改名。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等待复核
- `DONE`：已经完成，并且任务文档已回写
- `CANCELLED`：取消，不做了，但必须写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选为 `[x]`
- 每完成一个任务，必须回写这里
- 涉及删旧接口、删旧表、删旧页面逻辑时，必须先写清迁移和验证方式

---

## 阶段 1：先把统一模型和接口边界钉死

- [x] 1.1 定义“集成 / 设备 / 实体 / 辅助元素”统一模型
  - 状态：DONE
  - 这一步到底做什么：把页面、接口、后端服务、数据库迁移将使用的统一对象模型定下来，先消灭“HA 设备”“音箱设备”“普通设备”三套说法。
  - 做完你能看到什么：后续任何插件接入都只需要声明自己产出哪些资源，不再新增平台特例页面。
  - 先依赖什么：无
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L87)
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 主要改哪里：
    - `apps/api-server/app/modules/integration_*`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
  - 这一步先不做什么：先不碰 UI 视觉实现，先把模型说清楚。
  - 怎么算完成：
    1. 有统一的集成实例和资源模型
    2. 音箱终端也能放进这个模型
  - 怎么验证：
    - 设计走查
    - 类型定义和接口草案自检
  - 当前执行说明：先落后端统一 schema 和前端统一类型，后续接口与页面都以这套对象为准，不再新增 HA/音箱专用模型。
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4、需求 5
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L87)

- [ ] 1.2 设计统一用户端接口，替换旧 HA 专用接口
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把 `ha-config`、`ha-candidates`、`sync/ha` 这类旧接口替换成统一的目录、实例、资源、动作接口。
  - 做完你能看到什么：前端不再需要 `HomeAssistant*` API 和类型。
  - 先依赖什么：1.1
  - 开始前先看：
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [devices.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/devices.py)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L146)
  - 主要改哪里：
    - `apps/api-server/app/api/v1/endpoints/`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
  - 这一步先不做什么：先不删旧接口实现文件，先把替换方案固定。
  - 怎么算完成：
    1. 新接口能够覆盖目录、实例、资源、动作四类需求
    2. 旧 HA 接口进入明确删除清单
  - 怎么验证：
    - 接口清单走查
    - 前后端字段映射检查
  - 当前执行说明：已新增 `/integrations/catalog`、`/integrations/instances`、`/integrations/resources`、`/integrations/page-view` 和统一动作接口；设置页里的 Home Assistant 配置表单走 `/ai-config/{household_id}/plugins/{plugin_id}/config`，同步动作走 `/integrations/instances/{id}/actions`，前端设置页里已经不再调用旧 `ha-config`、`ha-candidates`、`sync/ha`。
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 5、需求 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L146)

### 阶段检查

- [ ] 1.3 阶段检查：确认页面和后端都以统一模型为中心
  - 状态：TODO
  - 这一步到底做什么：检查后续改造是不是已经围绕“统一插件目录 + 实例 + 资源”展开，而不是在旧 HA 页面上继续缝缝补补。
  - 做完你能看到什么：团队不会在错误的模型上继续堆工作。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
  - 主要改哪里：当前 Spec 文档
  - 这一步先不做什么：不开始写视觉细节。
  - 怎么算完成：
    1. 没有关键模型缺口
    2. 没有继续保留 HA 特例的顶层结构
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1 至 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)

---

## 阶段 2：后端主链彻底收口到统一插件体系

- [ ] 2.1 给设备类插件接入统一插件配置，不再直读旧 HA 专表
  - 状态：IN_PROGRESS
  - 这一步到底做什么：让 `homeassistant` 插件改为读取统一插件配置实例，删除插件内部对 `HouseholdHaConfig` 和 `database_url` 偷读路径的依赖。
  - 做完你能看到什么：插件运行时终于像插件，而不是回库偷配置的特权模块。
  - 先依赖什么：1.3
  - 开始前先看：
    - [adapter.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/adapter.py)
    - [config_service.py](/C:/Code/FamilyClaw/apps/api-server/app/modules/plugin/config_service.py)
    - [models.py](/C:/Code/FamilyClaw/apps/api-server/app/modules/ha_integration/models.py)
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/homeassistant_device_action/`
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/ha_integration/`
  - 这一步先不做什么：先不删旧表，先让新配置链可运行。
  - 怎么算完成：
    1. 插件配置来自统一插件配置实例
    2. 插件执行不再依赖旧专表
  - 怎么验证：
    - 插件配置测试
    - grep 检查 `HouseholdHaConfig` 依赖面
  - 当前执行说明：`homeassistant` 插件已经改为读取真实集成实例上的插件配置；`plugin_config_instances.integration_instance_id` 和 `device_bindings.integration_instance_id` 已经落地，插件目录下的 runtime / connector / executor 都按实例读取配置和更新状态，旧 `HouseholdHaConfig` 桥接已移除。
  - 对应需求：`requirements.md` 需求 5、需求 6、需求 7
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L59)

- [ ] 2.2 建统一集成实例服务和资源查询服务
  - 状态：IN_PROGRESS
  - 这一步到底做什么：新增或重构后端服务，统一管理插件目录、集成实例、资源列表、资源详情。
  - 做完你能看到什么：页面可以只调用统一服务，不再分别找 HA、设备、音箱、上下文接口拼数据。
  - 先依赖什么：2.1
  - 开始前先看：
    - [devices.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/devices.py)
    - [ai_config.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/ai_config.py)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L48)
  - 主要改哪里：
    - `apps/api-server/app/modules/`
    - `apps/api-server/app/api/v1/endpoints/`
  - 这一步先不做什么：先不做前端页面。
  - 怎么算完成：
    1. 统一目录接口可列可搜
    2. 统一实例接口可增删改查
    3. 统一资源接口可按设备、实体、辅助元素查询
  - 怎么验证：
    - 后端集成测试
    - API 契约测试
  - 当前执行说明：真实 `integration_instances` 模型、仓储、接口和页面视图已经落地；`/integrations/instances/{id}/actions` 已按实例执行，`homeassistant` 已接通 `configure`、`device_candidates`、`device_sync`、`room_candidates`、`room_sync`，设备资源查询和绑定归属也已经按 `integration_instance_id` 收口。
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 5
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L48)

- [ ] 2.3 让音箱终端与声纹入口并入统一资源详情能力
  - 状态：TODO
  - 这一步到底做什么：把当前设置页里音箱发现、音箱详情、声纹入口从顶层页面逻辑剥出来，纳入统一资源或集成动作模型。
  - 做完你能看到什么：主页面不再出现音箱专区，但音箱能力没丢。
  - 先依赖什么：2.2
  - 开始前先看：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [SpeakerDeviceDetailDialog.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/components/SpeakerDeviceDetailDialog.tsx)
    - [SpeakerVoiceprintTab.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/components/SpeakerVoiceprintTab.tsx)
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/`
    - `apps/api-server/app/modules/voiceprint/`
    - `apps/user-app/src/pages/settings/components/`
  - 这一步先不做什么：先不优化视觉表现，先把模型收口。
  - 怎么算完成：
    1. 音箱资源通过统一资源接口可见
    2. 声纹入口迁入资源详情能力面板
  - 怎么验证：
    - 音箱资源接口测试
    - 声纹详情回归测试
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L78)

### 阶段检查

- [ ] 2.4 阶段检查：确认后端已经不再依赖 HA 特权链路
  - 状态：TODO
  - 这一步到底做什么：检查后端主链是不是已经真收口到统一插件体系，而不是表面多了一层接口，底下还是 HA 私货。
  - 做完你能看到什么：后端后续再接新插件时不会继续复制 HA 历史包袱。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
  - 主要改哪里：后端相关实现与测试
  - 这一步先不做什么：不开始删表，先确认迁移条件成熟。
  - 怎么算完成：
    1. 新主链完整
    2. 旧主链只剩待删除部分
  - 怎么验证：
    - 人工走查
    - grep 检查旧路径依赖
  - 对应需求：`requirements.md` 需求 5、需求 6、需求 7
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L255)

---

## 阶段 3：把 user-app 的设备与集成页重做成统一插件页面

- [ ] 3.1 重做页面信息架构，采用“集成 / 设备 / 实体 / 辅助元素”四视图
  - 状态：TODO
  - 这一步到底做什么：把当前页面从“HA 配置 + HA 导入 + 音箱管理 + 设备列表”的拼盘，改成统一的四视图结构。
  - 做完你能看到什么：页面顶层结构和 Home Assistant 类似，但内容是当前产品自己的插件体系。
  - 先依赖什么：2.4
  - 开始前先看：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - 用户给出的 Home Assistant 参考截图
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L36)
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/integrations/index.tsx`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
  - 这一步先不做什么：先不追求花哨视觉，先把结构和流程做对。
  - 怎么算完成：
    1. 有统一“添加集成”入口
    2. 有四个视图切换
    3. 页面不再把 HA 和音箱写成顶层模块
  - 怎么验证：
    - 页面截图走查
    - 交互冒烟测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L36)

- [ ] 3.2 实现“选择品牌或集成”弹层和动态配置流程
  - 状态：IN_PROGRESS
  - 这一步到底做什么：做出统一插件目录搜索和选择弹层，用户通过插件配置表单添加集成实例。
  - 做完你能看到什么：用户添加 `homeassistant` 时，走的是标准插件流程，不再是写死的 HA 配置对话框。
  - 先依赖什么：3.1
  - 开始前先看：
    - [PluginDetailDrawer.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/components/PluginDetailDrawer.tsx)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L146)
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/integrations/`
    - `apps/user-app/src/pages/settings/components/`
  - 这一步先不做什么：先不做插件市场，不做远程下载。
  - 怎么算完成：
    1. 弹层可搜索插件目录
    2. 可进入插件配置表单
    3. 可创建集成实例
  - 怎么验证：
    - 页面 E2E
    - 用户流程回放
  - 当前执行说明：设置页顶层已经改成实例驱动草稿：空状态只显示“通过实例添加设备”，可以先选插件，再按插件 `config_spec` 创建实例；前端类型、API 和 i18n 已经对齐，`npm.cmd --prefix ./apps/user-app run typecheck` 已通过。
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L146)

- [ ] 3.3 用统一资源视图替换 HA 导入和音箱管理区块
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把当前页面里的 HA 候选导入弹窗、房间导入、音箱发现和音箱详情入口，全部改成统一资源和实例动作的子流程。
  - 做完你能看到什么：页面里没有“HA 导入设备”“HA 导入房间”“新音箱”这种硬编码区块。
  - 先依赖什么：3.2
  - 开始前先看：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/integrations/index.tsx`
    - `apps/user-app/src/pages/settings/components/`
  - 这一步先不做什么：先不删除底层旧代码文件，先完成页面切换。
  - 怎么算完成：
    1. 页面主结构中已无 HA 专用模块
    2. 页面主结构中已无音箱专用模块
    3. 资源详情和实例动作能覆盖原有核心能力
  - 怎么验证：
    - 页面 grep 检查
    - 冒烟回归
  - 当前执行说明：Home Assistant 的设备候选、设备同步和“同步全部 / 仅同步选中”都已经切到统一实例动作链路，旧顶层 HA 区块已经不再作为主结构；但音箱相关入口还没并入实例资源流，这一项仍在进行中，不能标 DONE。
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L69)

### 阶段检查

- [ ] 3.4 阶段检查：确认用户已经看不到平台特例页面
  - 状态：TODO
  - 这一步到底做什么：从用户视角检查页面是不是已经真正变成统一插件页，而不是旧功能换皮。
  - 做完你能看到什么：产品层终于和技术目标一致。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
  - 主要改哪里：当前页面与测试
  - 这一步先不做什么：不开始删库，先确认用户流程已切换。
  - 怎么算完成：
    1. 页面顶层信息架构正确
    2. 添加、查看、同步、详情都走统一流程
  - 怎么验证：
    - 页面验收清单
    - 产品走查
  - 对应需求：`requirements.md` 需求 1 至 6
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)

---

## 阶段 4：迁移数据、删旧代码、删旧表

- [ ] 4.1 迁移旧 HA 配置和相关数据到统一插件结构
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把 `household_ha_configs` 和依赖它的配置迁移到统一插件配置实例，并补必要的数据回填。
  - 做完你能看到什么：旧 HA 配置数据不丢，新页面仍然能读到旧家庭的集成配置。
  - 先依赖什么：3.4
  - 开始前先看：
    - [20260311_0008_add_household_ha_configs.py](/C:/Code/FamilyClaw/apps/api-server/migrations/versions/20260311_0008_add_household_ha_configs.py)
    - [models.py](/C:/Code/FamilyClaw/apps/api-server/app/modules/plugin/models.py#L101)
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
  - 主要改哪里：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/plugin/`
  - 这一步先不做什么：先不 drop 旧表，先验证迁移结果。
  - 怎么算完成：
    1. 旧配置已迁移
    2. 新页面和插件链可读取迁移后的配置
  - 怎么验证：
    - Alembic 迁移测试
    - 迁移后回归测试
  - 当前执行说明：已新增 `20260316_0044_create_real_integration_instances.py`，会创建真实实例表、回填实例级插件配置和设备绑定归属，并删除 `household_ha_configs`；已在 PostgreSQL 上完成空库升级和从 `20260316_0043` 到 `head` 的增量升级校验。
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L121)

- [ ] 4.2 删除旧 HA 专用后端接口、schema、服务和前端类型
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把旧 `ha-config`、`sync/ha`、`HomeAssistant*` 类型和页面调用全部删掉，不再保留兼容外壳。
  - 做完你能看到什么：代码仓库里不会再出现误导性的旧入口。
  - 先依赖什么：4.1
  - 开始前先看：
    - [devices.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/devices.py)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
  - 主要改哪里：
    - `apps/api-server/app/modules/ha_integration/`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - `apps/user-app/src/pages/settings/`
  - 这一步先不做什么：不留下“暂时兼容”的死代码。
  - 怎么算完成：
    1. 旧 HA 专用接口已删除
    2. 旧 `HomeAssistant*` 类型已删除
    3. 页面不再调用旧 API
  - 怎么验证：
    - grep 检查关键字
    - 后端和前端回归测试
  - 当前执行说明：前端旧 `HomeAssistant*` 类型和旧 HA API 调用已经从设置页删除；后端旧 `devices/ha-*` / `sync/ha` / `rooms/ha-*` 路由已经删除，`app/modules/ha_integration/` 旧模块也已经从应用代码里删除，相关测试已改到插件目录新实现。
  - 对应需求：`requirements.md` 需求 6、需求 8
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L184)

- [ ] 4.3 删除旧 HA 专表和废弃结构
  - 状态：IN_PROGRESS
  - 这一步到底做什么：在迁移和回归都通过后，用 Alembic 正式 drop `household_ha_configs` 和其它已废弃结构。
  - 做完你能看到什么：数据库层也不再处于半旧半新的过渡态。
  - 先依赖什么：4.2
  - 开始前先看：
    - [20260311_0008_add_household_ha_configs.py](/C:/Code/FamilyClaw/apps/api-server/migrations/versions/20260311_0008_add_household_ha_configs.py)
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
  - 主要改哪里：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/db/models.py`
  - 这一步先不做什么：不绕过 Alembic 直接改库。
  - 怎么算完成：
    1. 旧表被 Alembic 删除
    2. 模型层不再引用旧表
  - 怎么验证：
    - 迁移脚本测试
    - schema 检查
  - 当前执行说明：旧 `household_ha_configs` 已经并入 `20260316_0044` 迁移的 drop 流程，`app/db/models.py` 也不再注册旧表；当前还差更大范围的回归，暂时不标 DONE。
  - 对应需求：`requirements.md` 需求 6、需求 7、需求 8
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L121)

### 阶段检查

- [ ] 4.4 阶段检查：确认旧世界已经真的被删干净
  - 状态：IN_PROGRESS
  - 这一步到底做什么：检查代码、接口、页面、数据库是不是已经没有旧 HA 特例残留。
  - 做完你能看到什么：这次改造终于不是“新旧并存”的过渡态。
  - 先依赖什么：4.1、4.2、4.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
    - 当前代码仓库 grep 结果
  - 主要改哪里：全仓库
  - 这一步先不做什么：不再新增范围。
  - 怎么算完成：
    1. 关键旧词和旧路径已清零
    2. 新页面、新接口、新迁移都通过验证
  - 怎么验证：
    - grep `ha-config|sync/ha|HomeAssistantConfig|household_ha_configs`
    - 全量回归测试
  - 当前执行说明：应用代码、测试代码和前端设置页里对 `ha_integration`、`HouseholdHaConfig`、旧 `sync/ha` 路由和旧 `HomeAssistantConfig` 类型的直接引用已经清零；但全量回归测试还没跑完，这一项先保持 IN_PROGRESS。
  - 对应需求：`requirements.md` 需求 6、需求 7、需求 8
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L255)

---

## 阶段 5：补验证、补文档、形成可交付验收

- [ ] 5.1 补全后端、前端、迁移三层测试
  - 状态：IN_PROGRESS
  - 这一步到底做什么：补齐统一目录、实例、资源、动作、页面和迁移相关测试，防止以后重新长回平台特例。
  - 做完你能看到什么：不是靠口头保证，而是有自动化护栏。
  - 先依赖什么：4.4
  - 开始前先看：
    - `apps/api-server/tests/`
    - `apps/user-app/src/pages/settings/components/__tests__/`
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L255)
  - 主要改哪里：
    - `apps/api-server/tests/`
    - `apps/user-app/src/pages/settings/**/__tests__/`
  - 这一步先不做什么：不新增业务能力。
  - 当前执行说明：已新增 `tests/homeassistant_test_support.py`，并回写多组后端测试到实例级链路；前端 `typecheck` 已通过，后端关键文件和相关测试已 `py_compile`，`tests.test_plugin_observation_ingest` 与 `tests.test_agent_memory_insight` 已通过，其他更重的回归还要继续补。
  - 怎么算完成：
    1. 后端统一主链有测试
    2. 页面核心流程有测试
    3. 迁移脚本有测试
  - 怎么验证：
    - 运行测试集
  - 对应需求：`requirements.md` 需求 8
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L255)

- [ ] 5.2 输出验收清单和清理证据
  - 状态：TODO
  - 这一步到底做什么：整理最终验收清单，明确哪些旧路径已删除、哪些页面已替换、哪些迁移已执行。
  - 做完你能看到什么：项目交付时不会再出现“我以为删了，但其实没删”的扯皮。
  - 先依赖什么：5.1
  - 开始前先看：
    - [docs/README.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/docs/README.md)
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
  - 主要改哪里：
    - `specs/005.4-设备与集成全插件化重构/docs/`
  - 这一步先不做什么：不在验收阶段新增功能。
  - 怎么算完成：
    1. 有验收清单
    2. 有清理证据
    3. 有迁移说明
  - 怎么验证：
    - 验收走查
  - 对应需求：`requirements.md` 需求 8
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md#L255)

### 最终检查

- [ ] 5.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 spec 已经把后端、前端、UI、数据库、迁移、删除旧代码和验证标准都写清楚，后续执行时不会靠猜。
  - 做完你能看到什么：接手的人打开任务就能开工，不需要再口头补背景。
  - 先依赖什么：5.1、5.2
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/tasks.md)
  - 主要改哪里：当前 Spec 全部文档
  - 这一步先不做什么：不再扩功能范围。
  - 怎么算完成：
    1. 关键任务都有明确输入、输出、边界和验证
    2. 删除旧代码和删表不是一句口号，而是有明确顺序
    3. 页面参考图和产品目标已经落到具体结构
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：[design.md](/C:/Code/FamilyClaw/specs/005.4-设备与集成全插件化重构/design.md)
