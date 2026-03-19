# 需求文档 - HA 彻底插件化收尾

状态：Draft

## 简介

现在真正卡住 HA 的，不是少一两个接口，也不是页面没改完，而是边界没收干净。

过去几轮已经把不少链路迁到了插件体系里，但仓库里仍然存在三类硬伤：

- 核心层还认识 `Home Assistant`，甚至直接 import HA 插件 runtime
- HA 插件还在直接依赖核心仓储、密钥解密和数据库连接
- spec 的任务状态和代码现状不完全一致，导致“看起来完成”掩盖了“实际上没清零”

这次收尾不追求再做新功能，而是把插件化最后一层假壳扒掉。

这份 Spec 服务三类人：

- 项目负责人：需要一个不会再被“差不多完成”糊弄过去的验收口径
- 维护者：需要明确哪些逻辑必须留在核心，哪些必须迁到插件
- 实施者：需要一份可以直接照着推进、照着回写、照着验收的作战清单

## 术语表

- **System**：FamilyClaw API Server 与 `user-app`
- **核心层**：`apps/api-server/app/modules/**`、`apps/api-server/app/api/**` 以及承担产品顶层语义的 `apps/user-app/src/**`
- **HA 插件**：`apps/api-server/app/plugins/builtin/homeassistant_*`
- **边界残留**：任何还让核心认识 HA 平台细节，或让插件偷读核心内部实现的代码、接口、文案、数据结构
- **白名单**：允许暂时保留 HA 专名或兼容桥接的目录、文件或调用点；白名单必须显式列出，不能口头默认
- **收尾证据**：用于证明这次不是“口头插件化”的 grep 结果、白名单清单、测试结果、迁移验证结果和剩余残留说明

## 范围说明

### In Scope

- 固化 HA 彻底插件化的完成定义和主验收口径
- 审计并清理核心层对 HA 的专名逻辑、平台特判和直接依赖
- 审计并清理 HA 插件对核心仓储、密钥、数据库内部实现的直接依赖
- 清理前端产品层中 HA 专名文案、类型、页面特判和插件 id 猜测逻辑
- 对齐 `005.1`、`005.4`、`005.6` 与当前代码现状，避免 spec 和实现继续漂移
- 以 grep、白名单、回归测试和迁移校验作为最终收尾证据

### Out of Scope

- 不新增 Home Assistant 平台能力
- 不新增米家、涂鸦等新平台接入
- 不重做整套设备产品交互，只处理为完成插件化必须做的前端收口
- 不以“先兼容着”作为长期方案；只能保留明确写入白名单的临时桥接

## 需求

### 需求 1：系统必须把这次收尾的主口径统一下来

**用户故事：** 作为项目负责人，我希望这次有唯一主 spec 和唯一完成定义，以便后续不会再出现“代码、spec、口头说法三套口径”。

#### 验收标准

1. WHEN 团队执行 HA 收尾 THEN System SHALL 以 `004.8.4` 作为本轮收尾总控 spec，以 `005.1` 作为原则来源、以 `005.4` 作为功能清理主战场。
2. WHEN `005.4` 中关键任务仍为 `IN_PROGRESS` 或 `TODO` THEN System SHALL 禁止把 HA 彻底插件化表述为完成。
3. WHEN 代码现状与 spec 任务状态不一致 THEN System SHALL 先回写 spec，再继续推进实现或验收。

### 需求 2：核心层必须停止认识 HA 平台细节

**用户故事：** 作为架构维护者，我希望核心层只认识统一协议和通用能力，以便后续接别的平台时不再继续堆平台分支。

#### 验收标准

1. WHEN 检查 `apps/api-server/app/modules/**` 和 `apps/api-server/app/api/**` THEN System SHALL 不再保留 HA 专名业务逻辑、HA 专用离线原因、`platform == "home_assistant"` 之类的平台特判，除非该处被列入白名单。
2. WHEN 核心需要执行设备控制、设备同步、房间同步或状态读取 THEN System SHALL 通过正式抽象接口与插件交互，而不是直接 import `homeassistant_*` runtime 或 client。
3. WHEN 未来新增一个平台 THEN System SHALL 不需要在核心主链里新增新的平台专名分支才能接入。

### 需求 3：HA 插件必须通过正式宿主协议工作

**用户故事：** 作为插件系统维护者，我希望 HA 插件像插件一样工作，而不是继续走特权后门，以便插件体系不是假的。

#### 验收标准

1. WHEN 检查 `apps/api-server/app/plugins/builtin/homeassistant_*/**` THEN System SHALL 不再直接 import `app.modules.*.repository`、`app.modules.plugin.config_crypto`，也不再依赖 `_system_context.database_url` 自建数据库会话读取核心表，除非有明确白名单。
2. WHEN HA 插件需要读取配置、集成实例、绑定信息或执行状态更新 THEN System SHALL 通过宿主提供的正式 contract、service 或 entrypoint 完成，而不是自己绕过边界偷读实现。
3. WHEN HA 插件被禁用、配置缺失或宿主 contract 不满足 THEN System SHALL 返回统一、可理解的错误，而不是退回核心私有逻辑。

### 需求 4：前端和产品层必须停止写死 HA 特例

**用户故事：** 作为产品维护者，我希望前端顶层只表现插件和资源，而不是继续把 HA 当产品一级概念写死，以便后续插件扩展不会越改越乱。

#### 验收标准

1. WHEN 检查 `apps/user-app/src/**` THEN System SHALL 不再保留 Home Assistant 顶层专名文案、`home_assistant_status` 之类的平台特有字段、按 `plugin_id == "homeassistant"` 猜图标或流程的分支，除非有明确白名单。
2. WHEN 页面展示集成、设备、资源和同步入口 THEN System SHALL 通过统一插件元数据和统一资源模型渲染，而不是把 HA 当独立产品页继续维护。
3. WHEN 用户执行配置、同步和设备查看 THEN System SHALL 继续走统一实例和统一资源链路，而不是退回旧 HA 专用接口或旧产品语义。

### 需求 5：迁移期必须保证单轨执行，不允许新旧逻辑并存失控

**用户故事：** 作为现网维护者，我希望迁移过程不破坏现有功能，也不出现新旧双轨同时生效，以便不会因为收尾再次把用户功能打坏。

#### 验收标准

1. WHEN 旧 HA 路径尚未完全清除 THEN System SHALL 明确哪些是临时桥接、哪些已经废弃，并用白名单记录，而不是默许代码长期双轨。
2. WHEN 同一请求触发配置、同步、控制或状态加载 THEN System SHALL 只走一条正式链路，不允许新旧链路双写、双查或互相兜底。
3. WHEN 迁移完成 THEN System SHALL 删除、冻结或明确封存所有旧 HA 专用入口，避免后续再被误用。

### 需求 6：收尾验收必须以证据为准，不以口头描述为准

**用户故事：** 作为项目负责人，我希望这次的完成状态能被直接验证，而不是再靠“基本完成”“大体收口”这种模糊说法。

#### 验收标准

1. WHEN 任一任务准备标记为 `DONE` THEN System SHALL 同时提供对应 grep 结果、白名单说明、测试结果和剩余残留清单。
2. WHEN 仓库中仍存在未授权的 HA 专名残留或插件越界调用 THEN System SHALL 阻止最终验收通过。
3. WHEN 最终宣布“HA 彻底插件化完成” THEN System SHALL 具备可追踪的收尾证据包，而不是只给变更说明。

### 需求 7：收尾完成后，spec 和文档必须和真实实现对齐

**用户故事：** 作为后续接手的人，我希望打开 spec 就能知道现状，以便不用重新猜哪些完成、哪些还没完成。

#### 验收标准

1. WHEN 完成一项收尾任务 THEN System SHALL 及时回写 `tasks.md` 中的状态、当前执行说明和验证方式。
2. WHEN `005.1`、`005.4`、`005.6` 与 `004.8.4` 的边界关系发生调整 THEN System SHALL 在对应 spec 或 README 里写清楚主从关系，不允许继续让旧 spec 冒充现行规则。
3. WHEN 最终交付完成 THEN System SHALL 让后续维护者能从 spec、docs 和验证证据一眼看出哪些目录禁止再写 HA 特例。

## 非功能需求

### 非功能需求 1：可维护性

1. WHEN 后续新增一个设备平台 THEN System SHALL 主要通过新增插件和少量宿主 contract 扩展完成，而不是复制 HA 这套历史路径。
2. WHEN 维护者阅读核心和插件代码 THEN System SHALL 能明显看出“核心只认协议，插件负责平台实现”。

### 非功能需求 2：可审计性

1. WHEN 任何人复核这次收尾 THEN System SHALL 能通过固定 grep、白名单和测试清单复现验收结论。
2. WHEN 任务从 `IN_PROGRESS` 变为 `DONE` THEN System SHALL 能追溯到对应证据，而不是只看到一个状态变化。

### 非功能需求 3：兼容与稳定性

1. WHEN 清理核心和插件边界 THEN System SHALL 不破坏现有配置、同步、控制和状态读取主流程，除非 spec 明确声明变更。
2. WHEN 某项旧路径必须临时保留 THEN System SHALL 明确写成白名单并标出删除条件，避免进入长期灰色状态。

## 成功定义

- `005.4` 中与 HA 彻底插件化直接相关的关键任务已全部回写，且没有关键 `IN_PROGRESS` 遗留
- 核心目录中的 HA 专名业务逻辑已清零，或只剩明确登记的白名单
- HA 插件不再直接依赖核心仓储、密钥解密和数据库内部实现
- 前端顶层不再保留 Home Assistant 特例入口、特例文案和特例类型
- 最终交付包含 grep 结果、白名单清单、测试结果、迁移校验和剩余残留说明
