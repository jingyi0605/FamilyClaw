# 设计说明 - 非网页会话来源识别与控制命令

状态：Draft

## 1. 先说结论

这次不搞花活，直接做三件事：

1. 给统一会话层增加正式的来源附属表
2. 增加统一的非网页入站命令解析服务
3. 把 `Telegram` 线程会话规则正式写死并补齐测试

核心原则很简单：

- 不污染现有 `conversation_messages` 主表
- 不破坏网页端现有链路
- 不让每个渠道自己发明命令语义

---

## 2. 现状判断

### 2.1 已经有的东西

- 渠道层已经有 `channel_inbound_events`、`channel_conversation_bindings`、`channel_deliveries`
- `Telegram` 插件已经能拿到 `message_thread_id`
- `conversation_bridge` 已经会把线程信息拼进 `external_conversation_key`
- 小爱/语音侧已经有内存注册表来追踪当前会话

### 2.2 现在真正缺的东西

- 统一会话层没有正式来源记录
- 语音终端缺持久化会话绑定
- 非网页端没有统一控制命令入口
- `Telegram` 线程虽然有底层字段，但没有明确的正式规则和回归边界

---

## 3. 数据层设计

### 3.1 新增 `conversation_turn_sources`

这张表只做一件事：给统一会话层的每个 turn 记录来源。

不把这些字段硬塞进 `conversation_messages`，因为来源信息是附属元数据，不是每条消息本体都需要强耦合持有的核心字段。硬塞进去只会把主表继续搞胖，还会把网页和非网页的差异污染到核心会话模型里。

建议字段：

- `id`
- `conversation_session_id`
- `conversation_turn_id`
- `source_kind`
- `platform_code`
- `channel_account_id`
- `voice_terminal_code`
- `external_conversation_key`
- `thread_key`
- `channel_inbound_event_id`
- `created_at`

约束建议：

- `conversation_turn_id` 唯一，保证一个 turn 只对应一条正式来源记录
- `conversation_session_id`、`platform_code`、`channel_account_id` 建必要索引，方便按会话和平台追查

### 3.2 新增 `voice_terminal_conversation_bindings`

这张表用来把小爱或其他语音终端“当前绑定到哪个会话”正式落库。

建议字段：

- `id`
- `household_id`
- `terminal_type`
- `terminal_code`
- `member_id`
- `conversation_session_id`
- `binding_status`
- `last_command_at`
- `last_message_at`
- `created_at`
- `updated_at`

唯一约束建议：

- `household_id + terminal_type + terminal_code`

这个设计的目的是把“当前终端会话”从内存注册表挪成数据库事实。内存缓存可以继续保留，但只能当加速层，不能再当真实状态。

### 3.3 Migration 策略

这次数据层改动必须至少包含一条 Alembic migration，内容包括：

- 创建 `conversation_turn_sources`
- 创建 `voice_terminal_conversation_bindings`
- 补必要索引和唯一约束

如果实现时发现需要补充枚举值或外键约束，也必须继续走 migration，不允许只改 ORM 模型。

---

## 4. 命令层设计

### 4.1 新增统一命令解析服务

新增一个统一服务，例如 `InboundConversationCommandService`。

它负责两件事：

1. 判断一条非网页入站消息是不是控制命令
2. 如果是，执行对应会话切换逻辑，并返回统一结果

不要把 `/new`、`/reset` 的判断塞回各个插件里。插件只负责把原始平台消息标准化，命令语义必须在统一层收口。

### 4.2 第一版支持的命令

第一版只支持：

- `/new`
- `/reset`

兼容策略：

- 支持带前缀斜杠的形式作为正式命令输入
- 具体渠道如果已有明确限制，也可以在标准化阶段把等价命令映射成统一命令字
- 第一版不支持自然语言猜命令，避免误判

### 4.3 命令语义

`/new` 和 `/reset` 在第一版都采用同一个核心行为：

- 创建一个新的 `conversation_session`
- 更新当前外部入口绑定，让后续消息进入新会话
- 保留旧会话和旧消息，不做删除

区别只保留在返回文案层：

- `/new`：强调“已开始新会话”
- `/reset`：强调“已重置当前上下文并切到新会话”

这样做的原因很直接：别造两套底层逻辑。语义不同，数据动作相同，简单才不容易烂。

### 4.4 命令作用范围

- 渠道入口：更新 `channel_conversation_bindings`
- 语音终端入口：更新 `voice_terminal_conversation_bindings`
- 网页入口：不走这套逻辑，继续保持现有网页行为

### 4.5 命令执行时机

标准流程建议改成：

1. 渠道插件把原始消息标准化
2. 统一桥接层先判断是否为控制命令
3. 如果是命令，直接执行会话切换并返回提示
4. 如果不是命令，再进入正常 `conversation turn` 处理

这样能避免把 `/new` 这类命令也送进模型，浪费 token 还搞乱历史。

---

## 5. Telegram 线程正式化设计

### 5.1 线程唯一键

正式规则固定为：

- 非线程消息：继续沿用当前 `external_conversation_key`
- 线程消息：在线程级唯一键中使用 `chat:{chat_id}#thread:{thread_id}`

这个规则必须在设计、代码和测试里统一，不允许这里一套、实现里一套。

### 5.2 会话绑定规则

- 同一 `chat` 下不同 `thread` 必须对应不同外部会话键
- 同一 `thread` 内重复消息默认复用当前会话绑定
- 线程内执行 `/new` 或 `/reset` 时，只更新当前线程对应的绑定
- 不能让线程命令误伤同一群组里的其他线程

### 5.3 对现有桥接层的要求

`conversation_bridge` 需要从“现在顺手拼了个 thread key”升级成“明确依赖 thread 规则做正式绑定”。

至少要做到：

- 线程 key 生成逻辑集中在一个地方
- 私聊、普通聊天、线程聊天三种情况都有稳定分支
- 线程命令执行后，绑定更新可重复验证

### 5.4 兼容性要求

- 已有 `Telegram` 私聊行为不能变
- 已有非线程聊天如果没有 `message_thread_id`，继续按原逻辑工作
- 任何线程正式化改动都不能影响其他渠道

---

## 6. 服务改动边界

预计会涉及这些区域：

- `apps/api-server/app/modules/channel/`
- `apps/api-server/app/modules/conversation/`
- `apps/api-server/app/modules/voice/`
- `apps/api-server/app/plugins/builtin/channel_telegram/`
- `apps/api-server/app/db/models.py`
- `apps/api-server/migrations/versions/`

第一版不引入新的前端页面。命令入口先走非网页消息本身。

---

## 7. 测试设计

### 7.1 数据层测试

至少覆盖：

- 新来源表写入成功
- 一个 turn 只写一条来源记录
- 语音终端绑定能创建、更新、重载

### 7.2 命令层测试

至少覆盖：

- `/new` 命令创建新会话
- `/reset` 命令创建新会话
- 普通文本不会被误判成命令
- 命令执行后不会继续走普通对话生成链路

### 7.3 Telegram 线程测试

至少覆盖：

- 同一 `chat` 不同 `thread` 分别进入不同会话
- 同一线程连续消息复用会话
- 线程内 `/new`、`/reset` 只影响当前线程
- 私聊和非线程既有测试继续通过

---

## 8. 风险与回避方案

### 风险 1：来源记录和现有会话写入顺序不一致

处理方式：

- 把来源记录写入放进统一桥接层同一事务里
- 如果 turn 创建失败，不允许留下孤儿来源记录

### 风险 2：命令解析误伤普通文本

处理方式：

- 第一版只认显式命令格式
- 不做自然语言猜测

### 风险 3：线程正式化改坏已有 Telegram 行为

处理方式：

- 明确线程与非线程分支
- 先补测试再改行为
- 保证私聊和普通聊天回归覆盖

---

## 9. 最后的判断

这次设计没有引入新概念堆栈，只是把已经存在但散落的能力收口成正式规则。

数据层负责把事实存清楚。

命令层负责把行为收一致。

`Telegram` 线程正式化负责把“能跑”升级成“稳定可依赖”。
