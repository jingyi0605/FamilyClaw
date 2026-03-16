# 任务清单 - 非网页会话来源识别与控制命令

状态：Draft

## 说明

这份清单只做三件事，不扩散：

1. 数据层
2. 命令层
3. Telegram 线程正式化

每个任务都必须把 migration 和测试一起落地，不能只改逻辑不改表，也不能只改表不补测试。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经完成，等待复核
- `DONE`：已经完成并回写
- `CANCELLED`：明确取消，不再做

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每完成一个任务，都要立刻回写这份文件
- 如果卡住，就把卡点写清楚，不要装死

---

## 阶段 1：数据层

- [x] 1.1 数据层：来源表与语音终端会话绑定落地
  - 状态：DONE
  - 这一步到底做什么：给统一会话层补正式来源记录表，并把语音/小爱终端当前会话绑定改成数据库事实
  - 做完以后能看到什么结果：非网页 turn 进入 `conversation` 主链后，可以查到来源平台、外部会话和线程信息；语音终端重启后还能恢复之前绑定的会话
  - 先依赖什么：现有 `010` 主线里的渠道接入和 Telegram 基础链路已经可用
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/app/modules/voice/`
    - `apps/api-server/app/modules/channel/conversation_bridge.py`
    - `apps/api-server/app/db/models.py`
    - `apps/api-server/migrations/versions/`
    - `apps/api-server/tests/`
  - 这一步明确不做什么：不处理新的前端页面，不做跨平台会话合并
  - migration：
    - 新增 `conversation_turn_sources`
    - 新增 `voice_terminal_conversation_bindings`
    - 补索引、唯一约束和必要外键
    - migration 文件：`20260316_0041_create_conversation_turn_sources_and_voice_terminal_bindings.py`
  - 测试：
    - 新增数据层测试，覆盖来源记录幂等写入和语音终端绑定更新
    - 更新 channel bridge 测试，覆盖非网页 turn 来源正式落库
    - 更新 voice bridge 测试，覆盖语音侧会话绑定复用与来源记录接线
    - 回归跑过 `test_voice_pipeline.py` 和 `test_builtin_channel_plugins.py`
  - 完成说明：
    1. `conversation_turn_sources` 已落到 ORM、repository、service，并在 channel/voice 两条非网页链路里正式写库
    2. `voice_terminal_conversation_bindings` 已落到 ORM、repository、service，语音桥接会优先复用持久化绑定，不再只靠内存注册表
    3. 网页会话链路未改，Telegram 插件和既有语音管线回归测试已通过

---

## 阶段 2：命令层

- [x] 2.1 命令层：非网页端会话控制命令落地
  - 状态：DONE
  - 这一步到底做什么：增加统一入站命令解析服务，让非网页入口正式支持 `/new` 和 `/reset`
  - 做完以后能看到什么结果：用户可以直接在 Telegram、语音终端入口发送命令切到新会话，不需要回网页操作
  - 先依赖什么：1.1
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/inbound_command_service.py`
    - `apps/api-server/app/modules/channel/conversation_bridge.py`
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
    - `apps/api-server/tests/test_inbound_conversation_command_service.py`
    - `apps/api-server/tests/test_channel_conversation_bridge.py`
    - `apps/api-server/tests/test_voice_conversation_bridge.py`
  - 这一步明确不做什么：先不扩展更多命令，也不做自然语言猜命令
  - migration：
    - 本任务无新增 migration
    - 原因：`/new` 和 `/reset` 只复用现有会话表、渠道绑定表和语音终端绑定表，不需要新增字段或新表
  - 测试：
    - 新增命令解析单测，覆盖 `/new`、`/reset` 和普通文本不误判
    - 更新 channel bridge 测试，覆盖 `/new` 创建新绑定、`/reset` 切换已有绑定，且命令不会继续走正常 turn
    - 更新 voice bridge 测试，覆盖 `/new`、`/reset` 在 realtime turn 前短路执行
  - 完成说明：
    1. 新增统一命令服务，显式匹配 `/new`、`/reset` 及 Telegram 常见的 `/new@botname`、`/reset@botname`
    2. Channel 入口现在会在创建正常 turn 之前先解析命令；命令命中后只切绑定并返回确认文案，不会误送进模型链路
    3. Voice 入口现在会在 realtime turn 之前先解析命令；命令命中后只更新持久化终端绑定并返回确认文案

---

## 阶段 3：Telegram 线程正式化

- [x] 3.1 Telegram 线程正式化：线程级会话与管理收口
  - 状态：DONE
  - 这一步到底做什么：把 `Telegram` 的 `message_thread_id` 从“底层可透传”升级成正式线程级会话能力
  - 做完以后能看到什么结果：同一群组下不同线程各自有独立会话边界，线程里的 `/new`、`/reset` 只影响当前线程，回复也会回到当前线程
  - 先依赖什么：1.1、2.1
  - 主要改哪些文件：
    - `apps/api-server/app/modules/channel/conversation_routing.py`
    - `apps/api-server/app/modules/channel/conversation_bridge.py`
    - `apps/api-server/app/modules/channel/gateway_service.py`
    - `apps/api-server/tests/test_channel_conversation_bridge.py`
    - `apps/api-server/tests/test_channel_gateway_thread_delivery.py`
    - `apps/api-server/tests/test_builtin_channel_plugins.py`
  - 这一步明确不做什么：先不扩展到其他平台的线程模型，也不补富媒体线程能力
  - migration：
    - 本任务无新增 migration
    - 原因：线程级会话直接复用现有 `channel_conversation_bindings`、`conversation_turn_sources` 和 Telegram 插件已透传的 `thread_key`，不需要新增字段或新表
  - 测试：
    - 更新 bridge 测试，覆盖同一 `chat` 下不同 `thread` 会话隔离、同线程复用、线程内 `/reset` 只影响当前线程
    - 新增 gateway 线程投递测试，覆盖线程消息回复会带 `chat:{chat_id}#thread:{thread_id}` 目标
    - 回归跑过 `test_builtin_channel_plugins.py`，确认 Telegram 插件的线程 key 透传和发送参数不回退
  - 完成说明：
    1. 新增统一线程路由规则，线程唯一键固定为 `chat:{chat_id}#thread:{thread_id}`，绑定和投递都走同一套规则
    2. Channel bridge 现在会按线程 key 建立或复用绑定，同一 chat 下不同线程不会再共用一个会话
    3. Gateway 回复投递现在会带线程目标 key，线程内普通消息和 `/new`、`/reset` 都会回到当前线程
