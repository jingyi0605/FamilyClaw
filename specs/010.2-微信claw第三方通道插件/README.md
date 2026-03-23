# Spec 010.2 - 微信claw第三方通道插件

状态：Draft

## 这份 Spec 解决什么问题？

前面的 POC 已经把最关键的事实验证清楚了：

- 微信扫码登录可以跑通
- `getUpdates` 可以持续收消息
- 文本发送可以成功
- 回复链路依赖的 `context_token` 确实存在，而且确实关键

所以现在已经不是“能不能接”的问题，而是“怎么接才不把主仓库搞脏”的问题。

这次真正要解决的是下面三件事：

1. 把微信能力以第三方插件的方式接进 `FamilyClaw`
2. 把所有微信专属逻辑关进 `apps/api-server/plugins-dev`
3. 让宿主只负责通用 `channel` 插件运行时，不出现任何微信分支、微信 DTO、微信 worker、微信 token 逻辑

## 为什么现在做？

因为 POC 已经证明 transport 值钱，OpenClaw 路由层不值钱。

继续拖着不定边界，后面开发一定会犯两个低级错误：

- 为了快，把微信扫码、轮询、发消息逻辑直接塞进核心模块
- 为了省事，把 `weixin-agent-gateway` 整坨当成宿主内建能力搬进来

这两条路都很烂。第一条会污染核心代码，第二条会把 OpenClaw 耦合一并带进来。这个 Spec 就是先把这件事掐死。

## 核心判断

✅ 值得做：微信 transport 已经通过 POC，剩下的问题不是可行性，而是插件边界、持久化和运行时收口。

## 关键洞察

- 数据结构：真正需要长期保存的是账号登录态、轮询游标、`context_token`、媒体缓存和插件私有状态，而不是 OpenClaw 的 channel/runtime 抽象。
- 复杂度：最该砍掉的是 OpenClaw 耦合层，保留 transport，重新用 `FamilyClaw` 的 `channel` 契约接线。
- 风险点：`context_token` 现在默认只是进程内缓存。只要进程重启、轮询切换、异步延迟回复，它就会出事。

## 这次要交付什么？

- 一份正式的微信 claw 第三方插件需求文档
- 一份明确宿主边界、插件结构、运行方式和风险项的设计文档
- 一份可以直接排期执行的任务拆分
- 一份把 POC 结论和合规风险写清楚的补充文档

## 当前已补齐的两个宿主通用能力

### 1. `plugin-config-auth` 通用配置认证会话

这个能力是给“配置表单里的真实登录/扫码/第三方回调”用的，不是微信专属。
只要插件的 `config_preview` 会触发真实外部认证，比如扫码登录、OAuth 跳转、二次验证，就应该走它。

正式调用方式：

1. 前端调用 `POST /api/v1/ai-config/{household_id}/plugins/{plugin_id}/config/preview`
2. 请求体照常带 `scope_type`、`scope_key`、`values`、`secret_values`，如果这是某个 staged action，再额外带 `action_key`
3. 宿主创建或复用认证会话，在 `view.runtime_state.auth_session` 里返回 `id`、`status`、`callback_url`、`expires_at`
4. 插件用 `auth_session.callback_url` 生成真正的第三方认证链接或二维码，并把后续恢复登录所需的私有上下文放进 `auth_session.payload`
5. 前端轮询 `GET /api/v1/ai-config/{household_id}/plugins/{plugin_id}/config/auth-sessions/{session_id}`
6. 第三方平台回调宿主 `GET/POST /api/v1/ai-config/plugin-config-auth-sessions/{session_id}/callback?token=...`
7. 插件下一次继续跑 `config_preview` 时，带回 `auth_session_id`，再从 `auth_session.callback_payload` 继续后半段流程

这条链路的边界必须守住：

- 宿主管会话 ID、回调地址、回调落库和统一轮询
- 插件只管生成认证链接、消费回调结果、继续自己的平台登录流程
- 不能再让用户手工复制回调 URL 当正式主流程

### 2. 通用媒体 delivery 契约

这个能力是给 `channel.send` 的正式出站链路用的，也不是微信专属。
只要插件要发图片、音频、视频或文件，就必须走宿主统一的媒体 delivery 结构，不能再塞平台私有字段。

正式调用方式：

1. 宿主创建 delivery 时，统一写入 `text`、`attachments`、`metadata`
2. `attachments` 是平台无关列表，每项至少包含：
   - `kind`
   - `file_name`
   - `content_type`
   - `source_path` 或 `source_url`
   - `size_bytes`
   - `metadata`
3. 插件收到 `channel.send` 请求后，只从 `payload.delivery.attachments` 读取媒体输入
4. 插件自己处理厂商上传、下载、鉴权、转发，不把这些脏活倒灌回宿主
5. 如果插件支持入站媒体，也应该把标准化附件放进自己的归一化消息载荷里，而不是发平台私有 DTO 给宿主

这条链路的边界也必须守住：

- 宿主只提供统一附件结构和投递记录
- 插件自己处理平台上传协议
- 不支持的媒体类型就明确报错，不能静默吞掉

## 这次明确不做什么？

- 不在核心代码库里实现任何微信专属逻辑
- 不把 `weixin-agent-gateway` 原样并入宿主
- 不把 OpenClaw 的 `src/channel.ts`、`src/runtime.ts`、`src/messaging/process-message.ts` 之类耦合层继续沿用
- 不在这份 Spec 里承诺群管理、联系人同步、朋友圈、支付、企业能力等无关范围

## 和上层 Spec 的关系

这份 Spec 是 [`010-通讯通道插件与多平台机器人接入`](/C:/Code/FamilyClaw/specs/010-通讯通道插件与多平台机器人接入/README.md) 的子 Spec，也是对 [`010.1-非网页会话来源识别与控制命令`](/C:/Code/FamilyClaw/specs/010.1-非网页会话来源识别与控制命令/README.md) 的延续。

- `010` 解决的是“通道插件怎么接进来”
- `010.1` 解决的是“非网页来源进入统一会话层后怎么被正式承认”
- `010.2` 解决的是“微信 claw 这种带扫码登录和私有 transport 的通道，怎么在不污染宿主的前提下插件化落地”

## 主要文档

- `requirements.md`：把第三方插件边界、账号登录、收发链路、`context_token` 持久化、宿主通用能力补齐要求写清楚
- `design.md`：把插件包结构、Python/Node 双层适配、运行目录、状态持久化、动作接口和风险处理写清楚
- `tasks.md`：按“边界定稿 -> 插件骨架 -> 登录态 -> 收发链路 -> 管理与合规”拆阶段
- `docs/20260323-POC验证与风险结论.md`：记录当前已验证结论、技术风险和法律风险
- `docs/README.md`：说明本 Spec 的补充文档放什么
