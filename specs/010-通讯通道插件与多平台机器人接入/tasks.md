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

- [x] 3.1 第一批平台：`Telegram`、`Discord`、`飞书`
    - 状态：DONE
    - 完成说明：已把 `Telegram`、`Discord`、`飞书` 作为 builtin channel plugin 正式落地，分别补齐 `manifest.json` 和 `channel` 入口，并接到现有统一 gateway、成员绑定解析、`conversation` 主链、出站投递记录上。三个平台的差异都收在各自插件目录内，没有把平台判断散落到全局。额外补了一次很窄的 gateway 扩展：插件现在可以声明自定义 HTTP 响应，专门处理 `Discord interaction defer` 和 `飞书 challenge` 这类平台协议要求，但消息处理主链还是复用现有 `channel -> conversation -> delivery`，没有旁路重写聊天系统。
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
    - 已验证：
      - `python -m unittest tests.test_builtin_channel_plugins tests.test_channel_gateway_builtin_deferred tests.test_plugin_manifest tests.test_channel_gateway_api tests.test_channel_delivery_service`
    - 说明：
      - `Telegram` 第一版支持 webhook 文本消息与文本回发，支持按 `chat_id + thread` 还原回复目标
      - `Discord` 第一版按 interaction webhook 接入文本命令，先回 defer，再走现有主链并用 followup 完成回发；普通频道消息如果也要直接进主链，需要补一层长期运行的 Gateway/WebSocket 入站能力，这不是再加几行 webhook 解析能解决的
      - `飞书` 第一版现已同时支持明文 webhook challenge、`encrypt` 加密回调解包、文本消息标准化和文本回发
    - 对应需求：`requirements.md` 需求 2、3、4、5、7
    - 对应设计：`design.md` 1.4、2.3、3.3、8.1

- [x] 3.2 第二批平台：`钉钉`、`企业微信`
  - 状态：DONE
  - 完成说明：已新增 builtin `channel_dingtalk`、`channel_wecom_app`、`channel_wecom_bot` 三个插件目录，并补齐各自 `manifest.json` 与 `channel` 入口。`钉钉` 第一版已能把原始回调标准化成现有入站事件，并复用消息里的 `sessionWebhook` 做文本原路回发；`企业微信自建应用` 已支持回调握手、加密 XML 解包、文本入站标准化和通过应用凭证发文本消息；`企业微信群机器人` 则明确收成“只支持出站推送、不支持用户消息直接入站”的兼容边界，没有再把一堆平台特例污染进核心主链。
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
  - 已验证：
    - `python -m unittest tests.test_builtin_channel_plugins tests.test_channel_gateway_wecom_handshake tests.test_channel_gateway_builtin_deferred tests.test_plugin_manifest tests.test_channel_gateway_api tests.test_channel_delivery_service`
  - 说明：
    - `钉钉` 当前落地的是统一 HTTP gateway 可消费的文本事件与 `sessionWebhook` 原路回发闭环；如果后面要补真正常驻的 `stream/websocket` 运行时，需要单独扩一层通道长连接运行时，不是本任务里顺手多写几行代码就能带过去
    - `企业微信自建应用` 当前按 callback URL + `token / encodingAESKey / corp_id / corp_secret / agent_id` 跑文本主链，先保证文本往返闭环，不提前追复杂群聊与菜单事件
    - `企业微信群机器人` 当前明确只做出站推送兼容边界，后续如果要把它做成完整双向对话，需要重新设计入站来源，不在这一步硬拼
  - 对应需求：`requirements.md` 需求 2、3、4、5、7
  - 对应设计：`design.md` 1.4、2.3、8.2

- [x] 3.3 建平台账号探测、状态汇总和失败摘要接口
  - 状态：DONE
  - 完成说明：已新增正式 `channel_accounts` API，把平台账号列表、创建、更新、探测、单账号状态、最近投递和最近入站事件全部挂到 `ai-config/{household_id}` 下，并复用现有 `channel` 服务和 `delivery / inbound` 记录，不再让管理端自己拼数据。探测逻辑也统一收口到 `status_service`，由它调 `channel` 插件的 `probe` 动作并把结果回写到 `channel_plugin_accounts.last_probe_status / status / last_error_*`。目前 builtin 平台都已经补了 `probe`：`Telegram / Discord / 飞书 / 企业微信自建应用` 做真实凭证校验，`钉钉 / 企业微信群机器人` 先按当前接入模式做配置级探测，不硬凑不存在的主动探测协议。
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
  - 已验证：
    - `python -m unittest tests.test_channel_accounts_api tests.test_builtin_channel_plugins tests.test_channel_gateway_wecom_handshake tests.test_channel_gateway_builtin_deferred tests.test_plugin_manifest tests.test_channel_gateway_api tests.test_channel_delivery_service`
  - 说明：
    - 已落地接口包括：账号列表、创建、更新、`probe`、单账号状态、投递列表、入站事件列表
    - 接口路径全部挂在 `ai-config/{household_id}` 风格下，没有再开一套孤立管理路径
    - 当前还没有复杂报表，只提供管理端足够消费的状态摘要和最近失败信息
  - 对应需求：`requirements.md` 需求 2、6
  - 对应设计：`design.md` 2.3.5、3.3.1、5.3

- [x] 3.4 阶段检查：五个平台的落地边界是不是清楚了
  - 状态：DONE
  - 完成说明：已把五个平台当前的已落地边界、明确延期项和主要风险统一收口到 Spec 文档里，不再靠口头默认。`README.md` 现在直接说明当前阶段边界，`design.md` 已把平台落地边界和延期风险写成正式章节，`docs/20260314-五个平台落地边界与延期项.md` 则单独用人话把五个平台“现在做到哪、故意没做什么、后面怎么补”写清楚。这样后面继续做管理端或继续深挖平台能力时，不会再把“暂未实现”误当成“默认已经支持”。
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
  - 已验证：
    - 已人工走查五个平台插件目录、`tasks.md`、`README.md`、`design.md` 和边界说明文档
    - 已确认五个平台都能对照出“已落地 / 明确没做 / 后续怎么补”
  - 说明：
    - `Discord` 普通频道消息直连主链、`钉钉` 常驻流式接入、`wecom-bot` 双向入站 都被明确收成延期项，不再模糊处理
    - 富媒体、卡片、审批和复杂群事件统一列为后续扩展，不继续污染当前文本主链交付范围
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` 1.4、2.3、8.1、8.2

## 阶段 4：补 `user-web` 接入入口与文档，把交付收口

- [ ] 4.1 `user-web` 设置页新增“通讯平台接入”页面
  - 状态：TODO
  - 这一步到底做什么：在 `user-web` 设置界面里给管理员一个正式页面，沿用当前主题样式，把“通讯平台接入”挂到“设备与集成”下方，用来配置平台账号、查看状态、看最近错误
  - 做完你能看到什么：平台接入不再只能靠手动调接口，入口也不再挂在即将移除的 `admin-web`
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 2、6
    - `design.md` 2.2、3.3.1、5.3
    - `apps/user-web/src/pages/SettingsPage.tsx`
    - `apps/user-web/src/components/SettingsNav.tsx`
  - 主要改哪里：
    - `apps/user-web/src/pages/SettingsChannelAccessPage.tsx`
    - `apps/user-web/src/components/SettingsNav.tsx`
    - `apps/user-web/src/App.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
    - `apps/user-web/src/i18n/zh-CN.ts`
    - `apps/user-web/src/i18n/en-US.ts`
  - 这一先不做什么：先不做市场页和第三方安装流
  - 页面结构：
    1. 新增独立设置子路由 `/settings/channel-access`，不要继续塞进 `/settings/integrations`
    2. 设置导航新增“通讯平台接入”项，位置固定在“设备与集成”下方
    3. 页面正文分 4 块：顶部说明卡、平台账号列表区、新增/编辑账号弹窗、账号详情区
    4. 平台账号卡片至少展示平台、账号名、连接方式、状态、最近探测结果、最近错误、最近入站时间、最近出站时间
    5. 卡片动作至少保留 `编辑`、`立即探测`、`启用/停用`
  - 路由名：
    - 页面路由：`/settings/channel-access`
    - 页面组件：`SettingsChannelAccess`
    - 列表加载接口：`GET /api/v1/ai-config/{household_id}/channel-accounts`
    - 创建接口：`POST /api/v1/ai-config/{household_id}/channel-accounts`
    - 更新接口：`PUT /api/v1/ai-config/{household_id}/channel-accounts/{account_id}`
    - 探测接口：`POST /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/probe`
    - 详情接口：`GET /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/status`
    - 失败投递接口：`GET /api/v1/ai-config/{household_id}/channel-deliveries?channel_account_id={account_id}&status=failed`
    - 失败入站接口：`GET /api/v1/ai-config/{household_id}/channel-inbound-events?channel_account_id={account_id}&status=failed`
  - 接口字段清单：
    - 列表 / 卡片主数据：`ChannelAccountRead`
      - `id`、`plugin_id`、`platform_code`、`account_code`、`display_name`
      - `connection_mode`、`config`、`status`
      - `last_probe_status`、`last_error_code`、`last_error_message`
      - `last_inbound_at`、`last_outbound_at`、`created_at`、`updated_at`
    - 创建提交体：`ChannelAccountCreate`
      - `plugin_id`、`account_code`、`display_name`、`connection_mode`、`config`、`status`
    - 编辑提交体：`ChannelAccountUpdate`
      - 前端只主动写 `display_name`、`connection_mode`、`config`、`status`
      - `last_probe_status`、`last_error_*`、`last_*_at` 只读，不让前端瞎改
    - 账号详情区：`ChannelAccountStatusRead`
      - `account`
      - `recent_failure_summary.recent_failure_count`
      - `recent_failure_summary.last_error_code`
      - `recent_failure_summary.last_error_message`
      - `recent_failure_summary.last_failed_at`
      - `latest_delivery`
      - `latest_inbound_event`
      - `latest_failed_inbound_event`
      - `recent_delivery_count`
      - `recent_inbound_count`
    - 失败记录区：
      - 出站失败列表使用 `ChannelDeliveryRead[]`
      - 入站失败列表使用 `ChannelInboundEventRead[]`
  - 怎么算完成：
    1. 可创建、修改、探测、启停平台账号
    2. 可查看最近失败和状态摘要
    3. 页面入口出现在 `user-web` 设置导航里，位置在“设备与集成”下方，不是孤儿页
    4. 路由、页面结构、字段映射都已按 Spec 定死，不靠实现时临场发挥
  - 怎么验证：
    - 前端联调
    - `user-web` 手工回归
  - 对应需求：`requirements.md` 需求 2、6
  - 对应设计：`design.md` 2.2、3.3.1、5.3

- [ ] 4.2 在“通讯平台接入”页的对应平台账号下补成员绑定编辑区
  - 状态：TODO
  - 这一步到底做什么：在每个平台账号的详情区直接维护“家庭成员 <-> 外部通讯平台 ID”绑定，让系统能按来源消息准确识别是谁在说话
  - 做完你能看到什么：管理员能在 Telegram、Discord、飞书、钉钉、企业微信等账号配置里，直接把外部 ID 绑给对应家庭成员
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 3、6
    - `design.md` 2.3.2、3.3.2
    - `apps/user-web/src/pages/SettingsChannelAccessPage.tsx`
  - 主要改哪里：
    - `apps/user-web/src/pages/SettingsChannelAccessPage.tsx`
    - `apps/user-web/src/components/ChannelAccountBindingsPanel.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
    - `apps/user-web/src/i18n/zh-CN.ts`
    - `apps/user-web/src/i18n/en-US.ts`
  - 这一先不做什么：先不做批量导入绑定
  - 子块拆分：
    1. 绑定列表区
       - 在当前平台账号详情里展示已有绑定列表
       - 每行显示成员名、`external_user_id`、`external_chat_id`、备注、绑定状态、更新时间
       - 每行提供 `编辑`、`停用/恢复` 操作
    2. 新增/编辑绑定弹窗
       - 统一复用一个弹窗处理新增和编辑
       - 表单字段固定为 `member_id`、`external_user_id`、`external_chat_id`、`display_hint`、`binding_status`
       - 新增默认 `binding_status=active`
    3. 成员选择数据源
       - 从当前家庭成员接口读取候选成员，不手写死数据
       - 第一版只允许选择当前家庭内有效成员
       - 成员下拉要能显示用户可识别的信息，至少有姓名
    4. 绑定冲突提示
       - 冲突时要把后端返回的外部 ID 重复占用提示直接落到表单
       - 未绑定、加载失败、保存失败、账号未完成配置等状态都要在详情区给出可见反馈
  - 怎么算完成：
    1. 在某个平台账号详情里可以看、新增、修改、停用绑定
    2. 冲突和未绑定状态有清楚提示
    3. 绑定的核心字段直接围绕 `member_id + external_user_id (+ external_chat_id)`，不再绕成员页反查
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
    1. 协议、数据模型、平台批次、用户端接入入口都可追踪
    2. 每个阶段都能独立交付
    3. 延期项和风险明确写清楚
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
