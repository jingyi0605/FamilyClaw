# 任务清单 - 设备控制与家居接入插件化改造（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单是给后续实现的人直接开工用的，不是拿来装懂的。

你打开任意一个任务，应该立刻知道：

- 这一步到底改什么
- 做完以后系统里能看到什么结果
- 依赖什么现有模块
- 主要改哪些文件
- 这一步故意先不做什么
- 怎么验证是不是真的完成

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但必须写原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，都必须立刻回写这里
- 如果任务范围变了，先改任务描述，再继续做

---

## 阶段 1：先把统一协议和主链边界立住

- [x] 1.1 定统一动作协议、参数 schema 和高风险规则
  - 状态：DONE
  - 这一步到底做什么：把系统内部允许的动作、每个动作能带什么参数、哪些设备类型可用、哪些动作算高风险，一次性写清楚并落成正式注册表。
  - 做完你能看到什么：以后语音、场景、页面都只说统一动作名，不再有人直接传 `light.turn_on` 这种平台细节。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` §1.4、§3.2.1、§3.3.1
    - `apps/api-server/app/modules/device_action/schemas.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/device_action/`
    - 新增或重构 `apps/api-server/app/modules/device_control_protocol/`
  - 这一步先不做什么：先不改插件执行，不碰 HA 真实调用。
  - 怎么算完成：
    1. 统一动作定义能覆盖现有灯、空调、窗帘、音箱、门锁动作
    2. 参数校验和高风险规则已经集中收口
  - 怎么验证：
    - 单元测试覆盖动作定义和参数校验
    - 人工走查动作表，不再出现平台 service 名称
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` §1.4、§3.2.1、§3.3.1、§6.1、§6.3

- [x] 1.2 把设备绑定改成正式插件路由数据
  - 状态：DONE
  - 这一步到底做什么：给设备绑定补上 `plugin_id` 和必要版本信息，让系统以后按绑定找插件，不再按 `vendor` 猜平台。
  - 做完你能看到什么：一台设备到底归哪个插件管，这件事终于变成正式数据，而不是代码里临时猜。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §3.2.7、§4.1、§6.4
    - `apps/api-server/app/modules/device/models.py`
    - `apps/api-server/app/modules/ha_integration/service.py`
    - `apps/api-server/app/modules/device/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/device/models.py`
    - `apps/api-server/migrations/`
    - 绑定相关 service / repository
  - 这一步先不做什么：先不搬 HA 逻辑，只把路由数据结构补齐。
  - 怎么算完成：
    1. `DeviceBinding` 能明确记录负责插件
    2. 旧 HA 设备迁移后能补齐 `plugin_id`
  - 怎么验证：
    - Alembic migration 测试
    - 旧数据回填测试
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` §3.2.7、§4.1、§6.4

- [x] 1.3 建统一设备控制执行器，不再让核心直连 HA
  - 状态：DONE
  - 这一步到底做什么：新增 `DeviceControlService` 和 `DevicePluginRouter`，把权限、可控性、高风险确认、幂等、审计都收进统一主链，再从这里调插件。
  - 做完你能看到什么：所有控制请求都会先过同一套规矩，然后再进插件执行，不再有人直接调用 HA 模块。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4
    - `design.md` §2.3.1、§2.2、§3.3.1、§5.3
    - `apps/api-server/app/modules/device_action/service.py`
    - `apps/api-server/app/modules/plugin/service.py`
  - 主要改哪里：
    - 新增 `apps/api-server/app/modules/device_control/`
    - `apps/api-server/app/modules/device_action/service.py`
    - `apps/api-server/app/api/v1/endpoints/device_actions.py`
  - 这一步先不做什么：先不实现 HA 插件细节，只把主链换成插件调度框架。
  - 怎么算完成：
    1. `device_action` 不再直接 import HA 执行函数
    2. 审计、风险控制和超时都在统一主链收口
  - 怎么验证：
    - `device-actions` 集成测试
    - grep 检查核心主链不再直接调用 HA 执行函数
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` §2.2、§2.3.1、§3.3.1、§5.1、§6.2、§6.3

### 阶段检查

- [x] 1.4 阶段检查：统一控制主链是不是已经站稳
  - 状态：DONE
  - 这一步到底做什么：只检查动作协议、绑定数据和统一控制执行器是不是已经形成一条正式主链，不往平台细节里继续钻。
  - 做完你能看到什么：后面接 HA 真插件时，不需要再回头重拆控制主链。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4、需求 5
    - `design.md` §2.2、§2.3.1、§4.1、§6.1、§6.4
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不着急做 UI，不接新平台。
  - 怎么算完成：
    1. 上层调用已经只依赖统一动作协议
    2. 控制主链里不再直接写平台执行实现
  - 怎么验证：
    - 人工走查
    - 关键单元测试和集成测试回放
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4、需求 5
  - 对应设计：`design.md` §2.2、§2.3.1、§4.1、§6.1、§6.2、§6.4

---

## 阶段 2：把 HA 控制插件做成真插件

- [ ] 2.1 把 `homeassistant-device-action` 从 stub 改成真实执行插件
  - 状态：TODO
  - 这一步到底做什么：把现有 HA 控制逻辑搬进内置插件，让插件真正把统一动作映射成 HA service call。
  - 做完你能看到什么：HA 普通控制已经不是“插件壳”，而是真插件在执行。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` §3.4.1、§3.4.3、§6.2、§6.5
    - `apps/api-server/app/plugins/builtin/homeassistant_device_action/executor.py`
    - `apps/api-server/app/modules/ha_integration/service.py`
    - `apps/api-server/app/modules/ha_integration/client.py`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/homeassistant_device_action/`
    - 可能新增插件内私有 client / mapper 文件
  - 这一步先不做什么：先不删旧 HA 代码，先把真插件跑通。
  - 怎么算完成：
    1. 插件能执行灯、空调、窗帘、音箱等现有普通动作
    2. 插件返回标准执行结果和错误码
  - 怎么验证：
    - 插件单元测试
    - 统一控制主链调用 HA 动作插件的集成测试
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` §3.4.1、§3.4.3、§5.1、§6.2、§6.5

- [ ] 2.2 把 `homeassistant-door-lock-action` 做成真正的高风险插件
  - 状态：TODO
  - 这一步到底做什么：让门锁解锁等高风险动作也走正式插件，但高风险确认仍然保留在核心层。
  - 做完你能看到什么：高风险动作不是写死在核心，也不是插件自己决定放不放，而是核心把关、插件执行。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4、需求 6
    - `design.md` §3.4.1、§3.4.3、§5.3、§6.3、§6.5
    - `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/executor.py`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/`
    - `apps/api-server/app/modules/device_control/`
  - 这一步先不做什么：先不改 UI 确认流程，只补后端正式执行链。
  - 怎么算完成：
    1. 解锁等高风险动作必须先过核心确认
    2. 插件只做真实执行，不再自行判断权限
  - 怎么验证：
    - 高风险确认测试
    - 门锁动作插件执行测试
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 6
  - 对应设计：`design.md` §2.3.1、§3.4.1、§3.4.3、§5.3、§6.3、§6.5

- [ ] 2.3 切换 `device_action`、`voice`、`conversation`、`scene` 到统一控制执行器
  - 状态：TODO
  - 这一步到底做什么：把所有上层控制入口都改成调统一控制执行器，不再直接碰 HA 模块。
  - 做完你能看到什么：不管控制请求从哪条业务链进来，底下都是同一条插件执行主链。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 7
    - `design.md` §2.3.4、§3.3.4、§6.1、§6.2
    - `apps/api-server/app/modules/voice/fast_action_service.py`
    - `apps/api-server/app/modules/conversation/orchestrator.py`
    - `apps/api-server/app/modules/scene/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/voice/`
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/app/modules/scene/`
    - `apps/api-server/app/modules/device_action/`
  - 这一步先不做什么：先不改页面交互。
  - 怎么算完成：
    1. 上述入口都不再直接 import HA 执行实现
    2. 场景和语音仍能得到原有结果和审计记录
  - 怎么验证：
    - 语音快路径测试
    - 场景执行测试
    - 对话快动作测试
  - 对应需求：`requirements.md` 需求 4、需求 7
  - 对应设计：`design.md` §2.3.4、§3.3.4、§6.1、§6.2

### 阶段检查

- [ ] 2.4 阶段检查：HA 控制是不是已经真走插件
  - 状态：TODO
  - 这一步到底做什么：检查 HA 控制链是否已经由真实插件承载，而不是文档说插件、代码还是核心直连。
  - 做完你能看到什么：HA 控制这条主链终于名副其实。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4、需求 6、需求 7
    - `design.md` §2.3.1、§2.3.4、§3.4.3、§6.5
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不开始做同步链迁移。
  - 怎么算完成：
    1. 正式请求已经走 HA 真插件
    2. 原 stub 已被替换或冻结
  - 怎么验证：
    - grep 检查正式主链不再调用旧 HA 执行函数
    - 集成测试回放
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 6、需求 7
  - 对应设计：`design.md` §2.3.1、§2.3.4、§3.4.3、§6.5

---

## 阶段 3：把 HA 接入和同步主链做成真插件

- [ ] 3.1 定统一设备候选和同步结果协议
  - 状态：TODO
  - 这一步到底做什么：先把候选设备、候选房间、同步设备项、同步房间项和失败项的标准结构定下来，别让每个平台插件各说各话。
  - 做完你能看到什么：后面不管是 HA 还是别的平台，核心都能用同一种方式吃同步结果。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` §2.3.2、§2.3.3、§3.2.5、§3.2.6、§3.3.2、§3.3.3
    - `apps/api-server/app/modules/ha_integration/schemas.py`
  - 主要改哪里：
    - 新增或重构 `apps/api-server/app/modules/device_integration/`
    - `apps/api-server/app/modules/ha_integration/schemas.py`
  - 这一步先不做什么：先不接 HA 真实拉取逻辑。
  - 怎么算完成：
    1. 候选和同步结果有稳定标准结构
    2. 核心已经能校验插件返回是否合法
  - 怎么验证：
    - 单元测试
    - 非法结果校验测试
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` §2.3.2、§2.3.3、§3.2.5、§3.2.6、§3.3.2、§3.3.3

- [ ] 3.2 把 `homeassistant-device-sync` 从 stub 改成真实接入插件
  - 状态：TODO
  - 这一步到底做什么：把现有 HA 设备候选、房间候选、设备同步、房间同步的数据抓取逻辑搬进 HA 接入插件。
  - 做完你能看到什么：HA 接入插件真的能拉平台数据，不再吐 demo 记录。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §3.4.2、§3.4.3、§6.2、§6.5
    - `apps/api-server/app/plugins/builtin/homeassistant_device_sync/connector.py`
    - `apps/api-server/app/modules/ha_integration/service.py`
    - `apps/api-server/app/modules/ha_integration/client.py`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/homeassistant_device_sync/`
    - 可能新增插件内 mapper / client helper
  - 这一步先不做什么：先不删旧核心同步逻辑，只先让真插件跑通。
  - 怎么算完成：
    1. 插件能返回真实候选设备、候选房间和标准同步数据
    2. 插件能覆盖现有 HA 支持设备类型的接入需求
  - 怎么验证：
    - 插件单元测试
    - HA 候选查询和同步集成测试
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` §2.3.2、§2.3.3、§3.4.2、§3.4.3、§6.2、§6.5

- [ ] 3.3 建统一设备接入服务，并切旧 HA API 到新主链
  - 状态：TODO
  - 这一步到底做什么：让现有 `ha-config`、`ha-candidates`、`sync/ha`、`rooms/sync/ha` 等接口内部改走统一接入服务 + HA 接入插件。
  - 做完你能看到什么：外面看起来还是原来的 HA 页面和接口，底下已经换成插件化同步主链。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5、需求 7
    - `design.md` §3.3.2、§3.3.3、§3.3.4、§4.2
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/pages/SettingsPage.tsx`
  - 主要改哪里：
    - 新增 `apps/api-server/app/modules/device_integration/`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - 视情况调整前端文案或类型
  - 这一步先不做什么：先不加全新的通用平台管理页面。
  - 怎么算完成：
    1. 现有 HA 同步接口已经内部改走插件
    2. 同步摘要、候选列表和错误返回保持可用
  - 怎么验证：
    - 设备同步接口集成测试
    - `user-web` 手工回放或构建检查
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 7
  - 对应设计：`design.md` §3.3.2、§3.3.3、§3.3.4、§4.2

### 阶段检查

- [ ] 3.4 阶段检查：HA 接入是不是已经真走插件
  - 状态：TODO
  - 这一步到底做什么：检查 HA 设备候选、设备同步和房间同步是否都由正式插件承载。
  - 做完你能看到什么：HA 接入这条链不再是假插件壳。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5、需求 6、需求 7
    - `design.md` §2.3.2、§2.3.3、§3.4.2、§3.4.3、§6.5
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：先不接新平台。
  - 怎么算完成：
    1. 设备候选和同步正式走插件
    2. 核心已只保留统一落库和摘要逻辑
  - 怎么验证：
    - grep 检查核心不再直接拉 HA registry
    - 同步主链集成测试
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6、需求 7
  - 对应设计：`design.md` §2.3.2、§2.3.3、§3.4.2、§3.4.3、§6.5

---

## 阶段 4：清理旧实现、补验证、给后续平台留标准接缝

- [ ] 4.1 冻结或删除核心里的 HA 设备实现层
  - 状态：TODO
  - 这一步到底做什么：把已经迁完的 HA 平台实现从核心主链剥掉，避免新旧逻辑继续并存。
  - 做完你能看到什么：核心里只剩统一协议、统一执行器和统一接入服务，不再有一大块 HA 设备实现层。
  - 先依赖什么：2.4、3.4
  - 开始前先看：
    - `requirements.md` 需求 6、需求 7
    - `design.md` §1.4、§2.2、§6.2、§6.5
    - `apps/api-server/app/modules/ha_integration/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/ha_integration/`
    - 相关 import 调用点
  - 这一步先不做什么：不删 HA 配置模型和必要 client，只有在确实已经迁进插件后再删实现层。
  - 怎么算完成：
    1. 核心里不再保留正式 HA 控制实现层和同步实现层
    2. 留下的少量代码只负责共享配置或底层通用 helper
  - 怎么验证：
    - grep 走查
    - 全量相关测试回归
  - 对应需求：`requirements.md` 需求 6、需求 7
  - 对应设计：`design.md` §1.4、§2.2、§6.2、§6.5

- [ ] 4.2 补齐自动化测试和迁移文档
  - 状态：TODO
  - 这一步到底做什么：把控制主链、同步主链、插件结果校验、异常路径、旧数据迁移和回填方式都补成正式测试和文档。
  - 做完你能看到什么：这次重构不是靠口头保证，而是有回归保障和接手文档。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` §7、§8
    - `apps/api-server/tests/`
  - 主要改哪里：
    - `apps/api-server/tests/`
    - `specs/005.1-设备控制与家居接入插件化改造/docs/`
  - 这一步先不做什么：不扩新功能，只补验证和迁移说明。
  - 怎么算完成：
    1. 关键主链都有自动化测试
    2. 数据迁移和回填步骤有清楚文档
  - 怎么验证：
    - 跑测试集
    - 人工按文档回放一次迁移步骤
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §7、§8

- [ ] 4.3 给未来新平台留最小接入模板
  - 状态：TODO
  - 这一步到底做什么：把“一个新平台插件最少要实现什么”写成模板或开发说明，确保后续接米家、涂鸦时不会再把逻辑塞回核心。
  - 做完你能看到什么：后面接新平台时，开发者知道该写动作插件、接入插件、标准 payload 和结果结构，而不是重新发明轮子。
  - 先依赖什么：4.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3
    - `design.md` §3.4、§6.1、§6.2
    - `docs/开发者文档/插件开发/`
  - 主要改哪里：
    - `docs/开发者文档/插件开发/`
    - 当前 Spec 的 `docs/`
  - 这一步先不做什么：不真的实现新平台。
  - 怎么算完成：
    1. 新平台插件最小模板和接缝说明已经写清楚
    2. 文档能直接指导后续平台开发
  - 怎么验证：
    - 人工走查
    - 用模板检查能否覆盖一个假想平台接入需求
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §3.4、§6.1、§6.2

### 最终检查

- [ ] 4.4 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这次插件化改造真的已经形成稳定方案和可执行任务，不是“改了一半看起来很高级”。
  - 做完你能看到什么：需求、设计、任务、测试和迁移策略能一一对上，后续实现的人可以直接接手。
  - 先依赖什么：4.1、4.2、4.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再追加新范围。
  - 怎么算完成：
    1. 核心边界、插件边界和迁移顺序都清楚
    2. 关键任务都有需求和设计追踪
    3. 接手的人可以不靠口头背景直接开工
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
