# 设计文档 - 小爱音箱全插件化迁移
状态：Draft

## 1. 设计目标

这次设计只解决一件事：

把“小爱音箱还是平台特例”这件事彻底收口，让它变成和 HA 一样的正式插件实例。

迁移完成后，平台应当满足下面这条硬规则：

> 小爱音箱的发现、绑定、控制全部走标准插件链路，平台只保留通用 `speaker` 控制协议和声纹管理能力，不再允许历史特例成为主链。

## 2. 当前真实状态

### 2.1 现在已经有的东西

- 平台已经有正式插件注册、manifest、connector、action 执行器、实例、资源列表、设备控制路由
- `speaker` 设备类型已经在统一设备控制协议里定义了常见动作
- 声纹管理已经是平台能力，并且已经和设备、终端有关系模型
- HA 已经证明“实例驱动 + 插件 connector/action + 设备绑定”这条路是能跑通的

### 2.2 现在小爱的问题

当前小爱音箱仍然依赖旧专用链路：

- 发现由网关直接上报到专用 `/devices/voice-terminals/discoveries/*`
- 认领由专用 `claim_voice_terminal_discovery` 直接创建 `Device + DeviceBinding`
- 绑定没有正式 `plugin_id` / `integration_instance_id`
- 设备控制如果继续依赖旧 binding 结构，会和统一路由模型冲突
- 前端还残留小爱专用 discovery API 定义，但主页面已经在往集成页主链收口

问题不在“有没有功能”，而在“数据结构和入口已经分叉”。

## 3. 设计原则

### 3.1 只有一条正式主链

- 集成先有实例
- 实例再产出候选设备
- 候选设备再形成正式绑定
- 正式绑定再进入统一设备控制路由

不允许小爱继续保留一条“只给自己走的特例捷径”。

### 3.2 平台保留通用能力，插件只做适配

平台继续负责：

- `speaker` 动作协议定义
- 设备控制统一入口
- 设备页与设备日志
- 声纹管理与声纹相关数据模型

小爱插件负责：

- 发现外部音箱
- 把候选信息翻译成平台能理解的候选设备
- 把平台统一动作翻译成网关或终端调用

### 3.3 不为单一插件写死入口

这次不能把“让小爱进正式链路”做成另一个名字更花的特例。

需要抽出来的，是“任何注册插件如何声明自己支持实例化、发现候选设备、同步设备、执行动作”。

### 3.4 旧代码必须退出，不搞双轨制

迁移期间允许短暂兼容，但兼容层不是主链。

Spec 的完成标准之一，就是把旧小爱专用入口删掉，避免新旧两套代码一起活着。

## 4. 目标架构

## 4.1 目标链路

```text
open-xiaoai-gateway
  -> 平台统一的插件发现上报入口
  -> 小爱插件候选设备数据源
  -> 集成实例 actions / sync
  -> 正式 Device + DeviceBinding(plugin_id + integration_instance_id)
  -> 统一 device_action / device_control 路由
  -> 小爱插件 action executor
```

### 4.2 插件边界

建议新增一个正式内置插件目录，例如：

- `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/manifest.json`
- `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/connector.py`
- `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/executor.py`
- 如有必要再补 `runtime.py` 或 `adapter.py`

该插件至少声明：

- `connector`
- `action`

如果后续需要记忆摄入或仪表盘卡片，再按 manifest 能力继续扩展，但这次不是必须项。

### 4.3 实例建模

这次先把实例语义钉死：

- **一个小爱 gateway 实例允许管理多台音箱**
- 平台的 discovery 和 binding 必须按“一个实例下可出现多个终端候选项”来建模
- 不允许把实例继续偷换成“单音箱单实例”的隐式前提

这样定不是拍脑袋，而是基于当前 `open-xiaoai-gateway` 代码现实：

- 文本消息处理是按每个终端连接各自维护 `GatewayRuntimeState`
- 音频流上报事件带 `terminal_id + session_id`
- 播放控制命令也是按 `terminal_id` 精确分发

所以从网关事件模型看，它更接近“单进程、多终端连接、多音箱管理”，而不是“一个 gateway 进程只服务一台音箱”。

但是这里必须把话说完整：

- **这个判断目前只基于现有代码结构和事件模型**
- **还没有经过多音箱绑定的真实测试**
- 也就是说，我们现在可以按“一个 gateway 实例允许管理多台音箱”设计正式主链，但不能把它写成“已经被多音箱绑定场景验证通过”

因此这次设计要求是：

1. discovery 结构必须允许同一实例下返回多台音箱候选
2. binding 结构必须允许同一实例下落多条正式 `DeviceBinding`
3. 验证阶段必须补“多音箱绑定”测试，作为这条建模成立的真实回归依据
4. 在多音箱绑定测试补齐前，文档和代码注释都不能宣称这条能力已经被完整验证

## 5. 数据结构设计

### 5.1 正式绑定结构

小爱音箱迁移后生成的 `DeviceBinding` 必须具备：

- `plugin_id = open_xiaoai_speaker`
- `integration_instance_id = 对应的小爱实例 id`
- `platform = open_xiaoai`
- `external_device_id = 小爱终端的稳定外部 id`
- `external_entity_id = 小爱终端的稳定主实体 id 或等价 key`
- `capabilities = 插件标准化后的能力快照`

这样做的目的只有一个：让设备资源页、设备控制页、设备日志页都不用再知道“小爱是特例”。

### 5.2 发现数据

当前内存注册表不够稳，也不够通用。

推荐新增一张通用发现表，名称以实现时最终命名为准，这里先称为 `integration_discoveries`。

建议字段：

- `id`
- `plugin_id`
- `discovery_key`
- `discovery_type`
- `status`
- `payload`
- `external_device_id`
- `external_entity_id`
- `adapter_type`
- `last_seen_at`
- `created_at`
- `updated_at`
- `claimed_device_id` 或等价关联字段

目的不是为了再造平台，而是解决两个实际问题：

1. 小爱发现信息不能只活在内存里
2. 其他插件以后也需要一个正式 discovery 承载模型

如果实现阶段证明可以复用现有持久化模型并且不绕，那就优先复用；如果没有，就老老实实建表并走 Alembic。

### 5.3 平台能力保留

以下数据和逻辑不迁到插件：

- `speaker` 设备类型
- `speaker` 动作协议定义
- 设备页实体控制结构
- 声纹 enrollment / profile / summary 相关模型
- 设备操作记录

插件只消费这些能力，不复制这些能力。

## 6. 服务与接口设计

### 6.1 集成目录与实例创建

当前 `integration.service` 里存在硬编码只认 HA 的逻辑。

这里需要改成：

- 是否能作为“集成插件”展示，来自插件注册表与 manifest 能力，而不是固定插件 id
- 是否支持 `sync / claim / repair / configure`，来自插件声明与实例状态，而不是 `if plugin.id == "homeassistant"`

设计要求：

1. 平台列出所有已注册且声明可实例化的插件
2. 每个插件实例可声明自己支持哪些资源和哪些动作
3. 小爱与 HA 只是两个普通插件实例，不再在服务层拥有特殊身份

### 6.2 候选设备与发现

平台需要支持插件返回统一候选设备结果。

建议沿用当前 connector 返回候选设备与同步结果的思路，但把“只有 HA 支持这些 sync_scope”改成按插件能力分发。

小爱插件的 connector 最低要支持：

- 列出待添加音箱候选项
- 根据选中的候选项创建或更新正式绑定

候选项建议最少包含：

- 外部设备 id
- 外部主实体 id
- 展示名称
- 型号
- 序列号或稳定标识
- 当前在线状态
- 房间建议值
- 已绑定状态

### 6.3 设备控制

设备控制入口继续使用平台现有统一入口。

平台职责：

1. 根据 `device_id + entity_id` 找到正式 binding
2. 根据 `binding.plugin_id` 选择插件
3. 根据平台 `speaker` 动作协议完成动作校验、归一化、审计

小爱插件 executor 职责：

1. 把 `turn_on / turn_off / play_pause / set_volume` 等平台动作翻译成网关或终端可理解的调用
2. 返回统一成功或失败结果
3. 不重定义平台动作语义

### 6.4 网关到平台的发现上报

网关不应该继续长期依赖 `/devices/voice-terminals/discoveries/*` 这套专用 API。

迁移后的目标是：

- 网关把发现事件上报到统一插件发现入口，或者上报到通用 discovery 接收服务
- 平台根据 `plugin_id / adapter_type` 写入正式 discovery 数据源
- 插件 connector 从该数据源读取候选设备

迁移阶段允许保留一个薄兼容层，但兼容层必须满足：

1. 不再直接创建正式绑定
2. 只负责把旧上报转存到新 discovery 数据源
3. 在迁移完成后可以整体删除

## 7. 前端设计

### 7.1 集成页

小爱音箱的添加入口应当回到集成页主链。

目标效果：

- 用户在集成页看到“小爱音箱”正式插件
- 用户先创建实例
- 再在该实例下查看待添加音箱
- 再选择并添加到当前家庭

不再保留“设置页里还有一套小爱待认领入口”的双轨体验。

### 7.2 设备详情页

小爱音箱一旦成为正式 `speaker` 设备，设备详情页继续复用已有平台能力：

- 设备状态
- 控制动作
- 语音接管设置
- 声纹管理
- 操作日志

也就是说，这次不是重做一套“小爱详情页”，而是让它站到正式设备页上。

## 8. 迁移与删除策略

### 8.1 迁移顺序

1. 先补正式小爱插件与实例能力
2. 再补通用 discovery 数据源与候选设备读取
3. 再把小爱添加流程切到实例主链
4. 再把小爱控制切到正式 `plugin_id` 路由
5. 最后删除旧 discovery / claim / 前端旧 API / 无效专用入口

### 8.2 必删旧代码范围

迁移完成后，至少要审计并删除这些类别的旧代码：

- 旧的小爱专用 discovery endpoint
- 旧的小爱专用 claim 逻辑
- 旧的前端 `listVoiceTerminalDiscoveries / claimVoiceTerminalDiscovery` 调用与相关页面入口
- 旧的只靠 `platform == open_xiaoai` 维持主链的逻辑
- 旧的文档和注释里把特例链路当正式方案的描述

如果某段兼容层必须短暂保留，必须满足三条：

1. 有显式注释说明它是兼容层
2. 有明确删除条件
3. 不再承担主链职责

## 9. 风险与防护

### 9.1 最大风险

最大的风险不是“功能写不出来”，而是“把小爱特例包一层新名字继续留下”。

如果继续这样做，后面每接一个终端都会复制一遍。

### 9.2 主要防护

- 插件选择逻辑不能再写死插件白名单
- discovery 不能继续只放内存
- 正式绑定必须具备 `plugin_id + integration_instance_id`
- 设备控制必须只认正式绑定，不允许旧特例偷偷兜底
- 最终必须有旧代码清理清单和 grep 自检

## 10. 验证设计

至少需要覆盖这些验证：

1. 插件注册表里能看到小爱正式插件
2. 能创建小爱插件实例
3. 小爱实例能列出待添加音箱候选
4. 选中候选后能创建带正式 `plugin_id + integration_instance_id` 的绑定
5. 统一资源列表能看到该音箱
6. 统一设备控制入口能路由到小爱插件
7. 语音接管与声纹管理仍能挂在该设备上工作
8. 旧 discovery / claim 主链代码已删除或降为明确兼容层
9. 如果新增 migration，必须完成 PostgreSQL upgrade 验证

## 11. 成功标准

如果这次设计真正落地，最终应该能用一句话描述：

> 小爱音箱已经不再是平台特例，而是一个和 HA 同级、通过正式实例驱动进入平台的设备插件。

做不到这句话，就说明迁移还没完成。
