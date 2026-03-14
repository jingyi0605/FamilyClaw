# 任务清单 - 通讯通道插件与多平台机器人接入（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来堆黑话的，是拿来保证后续实现时不跑偏。

打开任何一个任务，都应该马上看明白：

- 这一步到底建什么
- 做完以后系统里能看到什么结果
- 依赖哪些现有模块
- 主要改哪些文件
- 这一步先故意不做什么
- 做完以后怎么验证

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等复核
- `DONE`：已完成并已回写
- `CANCELLED`：明确取消，不再做

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，都必须立刻回写状态
- 如果卡住，必须写清楚卡在哪，不要装死

## 阶段 1：先把通道插件底座立起来

- [x] 1.1 新增 `channel` 插件类型和通道 manifest 约束
  - 状态：DONE
  - 完成说明：已在现有插件系统里新增正式 `channel` 类型、`entrypoints.channel` 和 `capabilities.channel` 约束，不再把通讯平台继续伪装成普通 `connector`。通道插件现在必须显式声明 `platform_code`、`inbound_modes`、`delivery_modes`，缺入口或声明非法会直接拒绝。
  - 这一步到底做什么：给现有插件系统补一个正式的 `channel` 类型，把聊天平台从普通 `connector` 里分出来
  - 做完你能看到什么：系统能识别“这不是同步数据插件，而是通讯平台插件”
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 1.4、3.1、3.3
    - `specs/004.2-插件系统与外部能力接入/design.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/__init__.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不接任何真实平台，只把协议和校验边界立住
  - 怎么算完成：
    1. 插件系统能注册 `channel` 类型
    2. 通道插件缺少必要入口时会被明确拒绝
    3. `platform_code / inbound_modes / delivery_modes` 这些关键声明有正式校验
  - 怎么验证：
    - manifest 校验测试
    - 插件注册测试
  - 已验证：
    - `python -m unittest apps.api-server.tests.test_plugin_manifest`
    - `python -m unittest tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 1.4、3.1、3.3

- [x] 1.2 建平台账号、成员绑定、外部会话映射和入出站记录表
  - 状态：DONE
  - 完成说明：已新增 `channel_plugin_accounts`、`member_channel_bindings`、`channel_conversation_bindings`、`channel_inbound_events`、`channel_deliveries` 五类正式表结构，并补了 `channel` 模块模型与仓储。迁移严格按 `0029 / 0030 / 0031` 三步拆分，唯一约束直接覆盖账号码、外部用户标识、外部会话键、外部事件幂等等关键场景。
  - 这一步到底做什么：把通道接入需要的核心数据模型正式落到数据库
  - 做完你能看到什么：平台账号、成员绑定、外部会话映射、入站事件、出站投递都有正式表结构，不再靠临时 JSON 拼
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、3、4、5、6
    - `design.md` 3.2、3.4、4.1、4.2
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/`
    - `apps/api-server/app/db/models.py`
    - `apps/api-server/migrations/versions/`
  - 这一先不做什么：先不处理平台细节，只建通用模型
  - 怎么算完成：
    1. 五类核心表能表达账号、绑定、会话映射、入站、出站
    2. 唯一约束和索引能支撑幂等和查找
    3. migration 按 `0029 / 0030 / 0031` 三步拆分，而不是一坨塞完
  - 怎么验证：
    - Alembic migration 验证
    - repository 测试
  - 已验证：
    - `python -m unittest tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 2、3、4、5、6
  - 对应设计：`design.md` 3.2、4.1、4.2

- [x] 1.3 建通用通道服务：账号管理、绑定管理、幂等入站记录、出站投递记录
  - 状态：DONE
  - 完成说明：已补齐 `channel` 模块的通用 schema、账号服务、绑定服务和通用记录服务。平台账号创建现在会复用插件注册结果校验 `channel` 类型和连接模式；成员绑定统一从账号派生 `platform_code`，不再允许手填两份；入站事件记录具备按 `household + account + external_event_id` 幂等去重；出站投递记录也统一从通道账号派生平台信息。
  - 这一步到底做什么：把通道核心服务收口，后面平台插件和管理端都走同一套服务
  - 做完你能看到什么：平台账号、成员绑定、入站记录、出站记录都有正式 service 和 schema
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 2、3、5、6
    - `design.md` 2.2、3.3.1、3.3.2、3.3.5
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/account_service.py`
    - `apps/api-server/app/modules/channel/binding_service.py`
    - `apps/api-server/app/modules/channel/service.py`
    - `apps/api-server/app/modules/channel/repository.py`
    - `apps/api-server/app/modules/channel/schemas.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不接真实 webhook，只收口服务接口
  - 怎么算完成：
    1. 管理端和平台入口都能调用统一服务
    2. 重复事件能被幂等层挡住
    3. 平台账号、成员绑定的 schema 和现有 `Read / Create / Update` 命名风格一致
  - 怎么验证：
    - 单元测试
    - API 层集成测试
  - 已验证：
    - `python -m unittest tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 说明：本任务只收口服务接口，还没有正式 HTTP 管理端和 gateway 路由，因此 API 层集成测试放到后续接口任务一起补，不在这里伪造一层假接口。
  - 对应需求：`requirements.md` 需求 2、3、5、6
  - 对应设计：`design.md` 2.2、3.3.1、3.3.2、3.3.5

- [x] 1.4 阶段检查：通道底座是不是站稳了
  - 状态：DONE
  - 完成说明：已完成协议层、数据层、服务层三块底座检查。当前 `channel` 类型边界、五类核心表、通用服务接口和幂等约束已经闭合，后面接真实平台时不需要再回头改插件类型或重拆表结构，主要只剩平台适配和会话桥接。
  - 这一步到底做什么：只检查协议、表结构、核心服务是不是已经足够支撑后面接平台
  - 做完你能看到什么：后面开始接真实平台时，不需要再返工数据模型
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一先不做什么：不提前做页面，不提前接 webhook
  - 怎么算完成：
    1. 数据模型和服务边界清楚
    2. 幂等和追踪链条可验证
  - 怎么验证：
    - 人工走查
    - 核心测试回归
  - 已验证：
    - 已人工走查 `plugin manifest -> channel models -> channel services -> migrations`
    - `python -m unittest apps.api-server.tests.test_plugin_manifest`
    - `python -m unittest tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 1、2、3、5、6
  - 对应设计：`design.md` 2.2、3.2、4.1、4.2

## 阶段 2：把外部消息接到现有 AI 会话主链

- [x] 2.1 建统一入站消息标准化协议和平台 gateway 入口
  - 状态：DONE
  - 完成说明：已新增统一的标准化入站事件 schema、通道 gateway 服务和固定 webhook 路由 `POST /api/v1/channel-gateways/accounts/{account_id}/webhook`。gateway 现在只负责收原始请求、定位通道账号和插件、执行 `channel` 插件入口、拿回标准化事件并写入幂等入站记录，不把平台特例逻辑塞进核心 API。
  - 这一步到底做什么：给所有平台统一一套“标准化入站事件”格式，并建立统一 gateway 入口
  - 做完你能看到什么：平台回调先被标准化，再进入系统，而不是每个平台各写各的入口
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 1、4、5
    - `design.md` 2.3.3、3.3.3
    - `apps/api-server/app/modules/conversation/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/gateway_service.py`
    - `apps/api-server/app/api/v1/endpoints/channel_gateways.py`
    - `apps/api-server/app/api/v1/router.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做平台富媒体和复杂按钮回调
  - 怎么算完成：
    1. 所有平台都能产出统一入站事件
    2. 签名校验和幂等处理都在入口层完成
    3. webhook 路径固定为 `POST /api/v1/channel-gateways/accounts/{account_id}/webhook`
  - 怎么验证：
    - gateway API 测试
    - 重复事件测试
  - 已验证：
    - `python -m unittest tests.test_channel_gateway_api tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 1、4、5
  - 对应设计：`design.md` 2.3.3、3.3.3

- [x] 2.2 建成员绑定解析和外部会话映射桥接
  - 状态：DONE
  - 完成说明：已新增统一成员绑定解析逻辑和 `conversation_bridge` 桥接服务。系统现在会先按 `household + platform_code + external_user_id` 找有效绑定，再按 `household + channel_account + external_conversation_key` 复用或创建 `channel_conversation_bindings`。未绑定策略也已收口成统一规则：私聊固定提示并记 `ignored`，群聊默认忽略并记 `ignored`。
  - 这一步到底做什么：让平台消息能稳定找到内部成员和内部会话
  - 做完你能看到什么：同一个平台对话不会反复新建 session，也不会把消息投错人
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、4、5
    - `design.md` 2.3.2、3.2.3、4.1、6.1
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/binding_service.py`
    - `apps/api-server/app/modules/channel/session_bridge.py`
    - `apps/api-server/app/modules/channel/repository.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不处理跨平台会话合并
  - 怎么算完成：
    1. 已绑定成员能稳定进入自己的内部会话
    2. 同一平台会话键能稳定复用内部 session
    3. 未绑定成员有一致的默认处理策略，不会平台一套、平台一套
  - 怎么验证：
    - 绑定解析测试
    - 会话映射幂等测试
  - 已验证：
    - `python -m unittest tests.test_channel_conversation_bridge tests.test_channel_gateway_api tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 说明：`tasks.md` 这里写的是 `session_bridge.py`，但 `design.md` 明确用的是 `conversation_bridge.py`。本次按设计文档落地为 `conversation_bridge.py`，因为它和现有 `conversation` 主链命名一致，歧义更少。
  - 对应需求：`requirements.md` 需求 3、4、5
  - 对应设计：`design.md` 2.3.2、3.2.3、4.1、6.1

- [x] 2.3 复用现有 conversation 主链生成外部平台回复
  - 状态：DONE
  - 完成说明：外部文本消息现在已经通过 `ChannelConversationBridge.handle_inbound_message` 正式复用 `create_conversation_session` 和 `create_conversation_turn`，不再走任何简化问答旁路。统一 gateway 在收到标准化消息后，会把已绑定成员的消息继续送进现有 `conversation` 主链，生成和网页端同一套 assistant 输出、提案、动作与记忆处理结果。
  - 这一步到底做什么：把外部平台消息真正接到现有 `conversation` 会话和 turn 处理逻辑里
  - 做完你能看到什么：网页和外部平台面对的是同一个 AI，不会分脑子
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` 2.3.4、3.3.4、6.3
    - `apps/api-server/app/modules/conversation/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/conversation_bridge.py`
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不追求所有平台的实时流式分片输出
  - 怎么算完成：
    1. 外部消息复用现有会话和 turn 逻辑
    2. 记忆、提案、动作策略保持和网页端一致
  - 怎么验证：
    - 集成测试
    - 对话链回归测试
  - 已验证：
    - `python -m unittest tests.test_channel_conversation_bridge tests.test_channel_gateway_api tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` 2.3.4、3.3.4、6.3

- [x] 2.4 建统一出站投递与失败重试记录
  - 状态：DONE
  - 完成说明：已新增统一 `ChannelDeliveryService` 和 `status_service`。外部平台回复现在会先落一条 `pending` 投递记录，再尝试调用通道插件发送，最后把记录更新为 `sent / failed / skipped`，并保留 `provider_message_ref`、错误码、错误信息和尝试次数。重复入站事件不会重复发送；失败投递也支持按记录重试，并能按平台账号汇总最近失败摘要。
  - 这一步到底做什么：把 AI 输出封成平台出站消息，并把发送结果和失败信息正式落库
  - 做完你能看到什么：原路回复、失败可查、重试有依据
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 5、6
    - `design.md` 2.3.4、3.2.5、3.3.5、5.3
  - 主要改哪里：
    - `apps/api-server/app/modules/channel/delivery_service.py`
    - `apps/api-server/app/modules/channel/status_service.py`
    - `apps/api-server/app/modules/channel/`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做跨平台统一消息排版器
  - 怎么算完成：
    1. 每次外发都有投递记录
    2. 发送失败时能保留错误码和错误信息
    3. 能按平台账号维度汇总最近失败摘要
  - 怎么验证：
    - 投递成功测试
    - 投递失败和重试测试
  - 已验证：
    - `python -m unittest tests.test_channel_delivery_service tests.test_channel_conversation_bridge tests.test_channel_gateway_api tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 5、6
  - 对应设计：`design.md` 2.3.4、3.2.5、3.3.5、5.3

- [x] 2.5 阶段检查：外部会话到内部 AI 主链是不是打通了
  - 状态：DONE
  - 完成说明：第二阶段主链已经闭合：平台 webhook 进入统一 gateway，通道插件产出标准化事件，系统完成成员绑定解析、外部会话映射、未绑定默认策略、`conversation` 主链复用，以及原路出站投递记录。现在继续接真实平台时，主要剩平台适配和管理端接口，不需要再返工第二阶段的链路边界。
  - 这一步到底做什么：检查“平台消息进来 -> 找到成员 -> 复用内部会话 -> AI 回复 -> 原路发回去”这条主链是否闭合
  - 做完你能看到什么：后面接具体平台时，只需要补平台差异，不需要再改主链
  - 先依赖什么：2.1、2.2、2.3、2.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一先不做什么：不提前堆平台特例
  - 怎么算完成：
    1. 主链闭合
    2. 重复事件、未绑定、发送失败这几条异常链也可验证
  - 怎么验证：
    - 集成测试
    - 人工链路回放
  - 已验证：
    - 已人工走查 `gateway -> inbound event -> binding resolve -> conversation bridge -> delivery`
    - `python -m unittest tests.test_channel_delivery_service tests.test_channel_conversation_bridge tests.test_channel_gateway_api tests.test_channel_services tests.test_channel_repository tests.test_plugin_mounts tests.test_plugin_region_provider_runtime`
  - 对应需求：`requirements.md` 需求 3、4、5、6
  - 对应设计：`design.md` 2.3.3、2.3.4、4.1、5.3、6.1、6.3

## 阶段 3：按两批把平台插件真正落地

- [ ] 3.1 第一批平台：`Telegram`、`Discord`、`飞书`
  - 状态：TODO
  - 这一步到底做什么：基于 OpenClaw 官方实现思路，把三套主流平台先接通
  - 做完你能看到什么：至少三个平台能真正完成文本对话往返
  - 先依赖什么：2.5
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` 1.4、2.3、8.1
    - `C:\Code\openclaw\extensions\telegram`
    - `C:\Code\openclaw\extensions\discord`
    - `C:\Code\openclaw\extensions\feishu`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/channel_telegram/`
    - `apps/api-server/app/plugins/builtin/channel_discord/`
    - `apps/api-server/app/plugins/builtin/channel_feishu/`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不追求平台高级特性完全覆盖
  - 怎么算完成：
    1. 三个平台都能文本收发
    2. 三个平台都能完成成员绑定后的原路回复
  - 怎么验证：
    - 平台模拟测试
    - 端到端联调清单
  - 对应需求：`requirements.md` 需求 2、3、4、5、7
  - 对应设计：`design.md` 1.4、2.3、3.3、8.1

- [ ] 3.2 第二批平台：`钉钉`、`企业微信`
  - 状态：TODO
  - 这一步到底做什么：基于 `openclaw-china` 的实现思路，把中国常用企业通讯平台接上
  - 做完你能看到什么：国内常用平台也能按同一协议进入系统
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` 1.4、8.2
    - [openclaw-china](https://github.com/BytePioneer-AI/openclaw-china)
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/channel_dingtalk/`
    - `apps/api-server/app/plugins/builtin/channel_wecom_app/`
    - `apps/api-server/app/plugins/builtin/channel_wecom_bot/`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做所有企业平台高级审批、卡片和复杂组织目录
  - 怎么算完成：
    1. `钉钉` 能完成文本收发
    2. `企业微信自建应用` 能完成文本收发
    3. `企业微信机器人模式` 至少明确兼容边界和后补路线
  - 怎么验证：
    - 平台适配测试
    - 联调清单
  - 对应需求：`requirements.md` 需求 2、3、4、5、7
  - 对应设计：`design.md` 1.4、2.3、8.2

- [ ] 3.3 建平台账号探测、状态汇总和失败摘要接口
  - 状态：TODO
  - 这一步到底做什么：把平台账号状态、最近失败、最近投递结果收口成管理端可直接消费的 API
  - 做完你能看到什么：管理员不需要翻数据库就能看出哪一平台在坏
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 2、6
    - `design.md` 2.3.5、3.3.1、5.3
  - 主要改哪里：
    - `apps/api-server/app/api/v1/endpoints/channel_accounts.py`
    - `apps/api-server/app/modules/channel/status_service.py`
    - `apps/api-server/app/api/v1/router.py`
    - `apps/api-server/tests/`
  - 这一先不做什么：先不做复杂报表
  - 怎么算完成：
    1. 平台账号状态有统一摘要
    2. 最近失败和最近投递可直接被页面读取
    3. 接口路径与现有配置中心风格一致，挂在 `ai-config/{household_id}` 下
  - 怎么验证：
    - API 测试
    - 管理端联调
  - 对应需求：`requirements.md` 需求 2、6
  - 对应设计：`design.md` 2.3.5、3.3.1、5.3

- [ ] 3.4 阶段检查：五个平台的落地边界是不是清楚了
  - 状态：TODO
  - 这一步到底做什么：检查第一批和第二批平台的主链、差异点和延期项是不是已经写清楚
  - 做完你能看到什么：不会再出现“先把钉钉临时糊一下，后面再说”的脏路子
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一先不做什么：不扩大平台范围
  - 怎么算完成：
    1. 五个平台边界清楚
    2. 延期项明确写出，不藏雷
  - 怎么验证：
    - 人工走查
    - 分平台联调记录
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` 1.4、2.3、8.1、8.2

## 阶段 4：补管理端与接入文档，把交付收口

- [ ] 4.1 管理端新增“通讯平台接入”页
  - 状态：TODO
  - 这一步到底做什么：给管理员一个正式页面配置平台账号、查看状态、看最近错误
  - 做完你能看到什么：平台接入不再只能靠手动调接口
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 2、6
    - `design.md` 2.2、3.3.1、5.3
    - `apps/admin-web/src/pages/AiConfigPage.tsx`
  - 主要改哪里：
    - `apps/admin-web/src/pages/ChannelAccessPage.tsx`
    - `apps/admin-web/src/App.tsx`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/types.ts`
  - 这一先不做什么：先不做市场页和第三方安装流
  - 怎么算完成：
    1. 可创建、修改、探测、启停平台账号
    2. 可查看最近失败和状态摘要
    3. 页面路由能挂到当前管理端导航里，不是孤儿页
  - 怎么验证：
    - 前端联调
    - 手工回归
  - 对应需求：`requirements.md` 需求 2、6
  - 对应设计：`design.md` 2.2、3.3.1、5.3

- [ ] 4.2 成员页补多平台绑定管理面板
  - 状态：TODO
  - 这一步到底做什么：把成员与平台账号绑定能力挂到管理员真正会用的成员视图里
  - 做完你能看到什么：管理员能按成员直接维护 Telegram、Discord、飞书、钉钉、企业微信绑定
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 3、6
    - `design.md` 2.3.2、3.3.2
    - `apps/admin-web/src/pages/MembersPage.tsx`
  - 主要改哪里：
    - `apps/admin-web/src/pages/MembersPage.tsx`
    - `apps/admin-web/src/components/member/MemberChannelBindingsPanel.tsx`
    - `apps/admin-web/src/lib/api.ts`
  - 这一先不做什么：先不做批量导入绑定
  - 怎么算完成：
    1. 成员页可以看和改绑定
    2. 冲突和未绑定状态有清楚提示
  - 怎么验证：
    - 前端联调
    - 绑定冲突回归
  - 对应需求：`requirements.md` 需求 3、6
  - 对应设计：`design.md` 2.3.2、3.3.2

- [ ] 4.3 补平台接入文档、回调样例和联调清单
  - 状态：TODO
  - 这一步到底做什么：把后续真正接平台时最容易反复踩坑的配置、回调、联调信息写成文档
  - 做完你能看到什么：接手的人不会一遍遍重新猜平台参数和回调流程
  - 先依赖什么：4.2
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` 全文
    - `docs/README.md`
  - 主要改哪里：
    - `specs/010-通讯通道插件与多平台机器人接入/docs/`
    - `docs/`
  - 这一先不做什么：先不写平台营销文案
  - 怎么算完成：
    1. 每个平台有基本接入说明
    2. 有统一联调和验收清单
  - 怎么验证：
    - 人工走查文档
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` 全文

- [ ] 4.4 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 真正能指导分批实现，而不是只写了看起来很完整的一堆字
  - 做完你能看到什么：需求、设计、任务和后续验收都能一一对上
  - 先依赖什么：4.1、4.2、4.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一先不做什么：不再追加新平台和新范围
  - 怎么算完成：
    1. 协议、数据模型、平台批次、管理端入口都可追踪
    2. 每个阶段都能独立交付
    3. 延期项和风险明确写清楚
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
