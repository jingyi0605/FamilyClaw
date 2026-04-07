# 设计文档 - 微信claw插件Python运行时重写

状态：Draft

## 1. 概述

### 1.1 目标

- 用 Python 完整接管微信插件后端运行链路，删除 Node 运行时依赖
- 保持宿主接口、用户操作路径和插件状态摘要契约不变
- 在不污染宿主核心的前提下，把微信 transport 重新收口成单语言插件实现

### 1.2 覆盖需求

- `requirements.md` 需求 1：微信插件后端必须只依赖 Python 运行时
- `requirements.md` 需求 2：宿主接口和主要用户流程不能被破坏
- `requirements.md` 需求 3：Python transport 必须补齐现有正式能力
- `requirements.md` 需求 4：运行时状态必须兼容迁移
- `requirements.md` 需求 5：插件手册和开发规则必须同步更新

### 1.3 技术约束

- 后端：Python 3.11
- 前端：不新增微信专属页面逻辑，继续复用宿主现有通用 `channel-account` 渲染
- 数据存储：继续使用插件私有 SQLite、文件缓存和结构化日志
- 认证授权：继续复用宿主现有插件配置预检、账号级动作和通道动作入口
- 外部依赖：微信上游接口仍然存在，但 Python 实现不再依赖 Node bridge

## 2. 架构

### 2.1 系统结构

旧结构：

1. 宿主调用插件 Python 入口
2. Python 入口起 Node bridge
3. Node bridge 调 Node transport
4. Node transport 返回结果给 Python，再回宿主

新结构：

1. 宿主继续调用插件 Python 入口
2. Python 入口直接调用 Python transport 服务
3. Python transport 直接和微信上游交互
4. 结果按现有标准契约回给宿主

这次改动的核心不是“多写几段 Python”，而是砍掉整条跨语言调用链。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `plugin/action.py` | 继续处理账号级动作入口，负责参数校验和状态摘要组装 | 宿主动作 payload | 标准动作结果 |
| `plugin/channel.py` | 继续处理 `poll/send/probe` 入口 | 宿主通道 payload | 标准事件和投递结果 |
| `plugin/python_transport.py` | 新的 Python transport 主服务，直接处理微信协议细节 | 标准化 transport 请求 | 原始 transport 结果 |
| `plugin/weixin_api_client.py` | 负责具体 HTTP 请求、签名、超时和响应解析 | 上游请求参数 | 上游原始响应 |
| `plugin/runtime_state.py` | 继续负责登录态、游标、`context_token` 和缓存持久化 | 运行时状态操作 | SQLite/文件写入结果 |

### 2.3 关键流程

#### 2.3.1 扫码登录

1. 宿主继续通过 `config_preview` 触发 `start_login`
2. `action.py` 调用 Python transport 的登录入口
3. Python transport 请求微信上游，生成或获取二维码目标内容
4. Python 侧直接把二维码内容转成可展示的图片 data URL 或缓存文件
5. `action.py` 把统一 `status_summary + preview_artifacts` 返回给宿主

#### 2.3.2 登录状态刷新

1. 宿主触发 `get_login_status`
2. `action.py` 从运行时状态读出当前登录会话
3. Python transport 调微信上游查询状态
4. 插件更新登录态、错误信息和过期时间
5. 宿主继续只看到统一状态摘要

#### 2.3.3 消息轮询与发送

1. `channel.py` 继续处理 `poll/send`
2. Python transport 直接调用微信上游收消息或发消息
3. 插件继续复用现有标准化消息、媒体附件和 `context_token` 持久化逻辑
4. 宿主继续按现有 `channel` 契约消费结果

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `PythonTransportService`：统一封装登录、状态查询、轮询、发送和媒体处理
- `WeixinApiClient`：统一封装上游 HTTP 请求和错误翻译
- `RuntimeStateStore`：继续保存登录态、游标、`context_token` 和媒体缓存
- `CompatibilityAdapter`：负责把旧状态字段映射到新实现需要的内部结构

### 3.2 数据结构

覆盖需求：2、3、4

#### 3.2.1 `TransportLoginSession`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `channel_account_id` | `str` | 是 | 账号作用域 | 不为空 |
| `login_session_key` | `str` | 是 | 登录会话标识 | 与现有状态字段兼容 |
| `login_qrcode` | `str \| None` | 否 | 上游二维码原始内容 | 允许为空 |
| `qr_code_url` | `str \| None` | 否 | 可展示二维码图片地址或 data URL | 用于宿主预览 |
| `status` | `str` | 是 | `waiting_scan/scan_confirmed/active/expired/not_logged_in` | 继续沿用现有枚举 |
| `api_base_url` | `str \| None` | 否 | 当前上游地址 | 便于后续查询 |

#### 3.2.2 `TransportMessageEnvelope`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `external_event_id` | `str` | 是 | 外部事件唯一标识 | 轮询去重依赖 |
| `conversation_key` | `str` | 是 | 会话标识 | 不为空 |
| `external_user_id` | `str` | 是 | 外部用户标识 | 不为空 |
| `text` | `str \| None` | 否 | 文本内容 | 可为空 |
| `attachments` | `list[dict]` | 否 | 标准附件列表 | 与宿主契约一致 |
| `context_token` | `str \| None` | 否 | 用于回复的上下文令牌 | 可持久化 |

### 3.3 接口契约

覆盖需求：1、2、3、4

#### 3.3.1 `PythonTransportService.start_login(...)`

- 类型：Function
- 路径或标识：`plugin.python_transport.start_login`
- 输入：账号标识、运行时目录、当前基础配置
- 输出：`login_session_key`、二维码内容、展示用二维码结果、状态摘要所需字段
- 校验：必须有账号作用域；基础配置缺失时给出字段级错误
- 错误：`invalid_action_payload`、`transport_upstream_error`、`qr_generation_failed`

#### 3.3.2 `PythonTransportService.get_login_status(...)`

- 类型：Function
- 路径或标识：`plugin.python_transport.get_login_status`
- 输入：登录会话快照、运行时目录、必要的上游连接信息
- 输出：最新登录状态、账号标识、必要的 token 或用户信息
- 校验：没有登录会话时直接返回统一未登录结果
- 错误：`transport_upstream_error`、`login_state_invalid`

#### 3.3.3 `PythonTransportService.poll(...)`

- 类型：Function
- 路径或标识：`plugin.python_transport.poll`
- 输入：登录态、轮询游标、运行时目录
- 输出：消息列表、下一轮游标、可选状态变更
- 校验：必须存在有效登录态
- 错误：`not_logged_in`、`transport_upstream_error`

#### 3.3.4 `PythonTransportService.send(...)`

- 类型：Function
- 路径或标识：`plugin.python_transport.send`
- 输入：登录态、文本、附件、`context_token`
- 输出：投递结果、provider message ref、必要的错误信息
- 校验：文本和附件至少有一个；`context_token` 缺失时给出明确错误
- 错误：`invalid_delivery`、`context_token_missing`、`context_token_invalid`、`transport_upstream_error`

## 4. 数据与状态模型

### 4.1 数据关系

这次不重做状态模型，只做三件事：

1. 保留现有 SQLite 表和缓存目录的主体结构
2. 把原来只服务 Node 子层的中间结果裁掉
3. 把 Python transport 所需字段直接落到现有插件私有状态里

原则很简单：

- 能复用的状态字段继续复用
- 必须新增的字段写清楚用途
- 只属于 Node bridge 的状态不再保留长期依赖

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `not_logged_in` | 当前没有可用登录态 | 初始状态、退出登录、状态清理 | 触发 `start_login` |
| `waiting_scan` | 已生成二维码，等待扫码 | `start_login` 成功 | 扫码确认、过期、手动清理 |
| `scan_confirmed` | 已扫码，等待微信侧确认 | 上游返回已扫码未确认 | 登录成功、过期、手动清理 |
| `active` | 当前账号已登录可收发消息 | 状态刷新或登录成功 | token 失效、手动退出、上游登出 |
| `expired` | 当前二维码或登录态已失效 | 上游返回过期或失效 | 重新生成二维码或重新登录 |

## 5. 错误处理

### 5.1 错误类型

- `transport_upstream_error`：微信上游返回异常、超时或不可达
- `login_state_invalid`：本地状态损坏，无法继续刷新登录状态
- `context_token_missing`：发消息时缺少可用上下文令牌
- `runtime_state_migration_failed`：旧状态无法安全迁移
- `qr_generation_failed`：二维码内容无法转换成宿主可展示的图片结果

### 5.2 错误响应格式

```json
{
  "detail": "微信登录状态查询失败，请稍后重试。",
  "error_code": "transport_upstream_error",
  "field": null,
  "timestamp": "2026-04-07T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：继续返回字段级错误，不把微信私有细节泄漏到宿主
2. 业务规则错误：优先返回统一错误码和可读中文说明
3. 外部依赖错误：记录插件私有日志，必要时把状态标记成 `expired` 或保留旧状态
4. 重试、降级或补偿：
   - 登录状态刷新失败时，不立刻抹掉旧状态
   - 轮询失败时保留旧游标
   - 发送失败时保留最近一次 `context_token` 状态，便于排障

## 6. 正确性属性

### 6.1 属性 1：宿主契约不变

*对于任何* 现有宿主调用 `config_preview`、`action`、`channel` 的地方，系统都应该满足：Python 重写后不需要宿主新增微信专属字段，也不要求宿主改接口。

**验证需求：** 需求 2、需求 3

### 6.2 属性 2：运行时单语言收口

*对于任何* 微信插件正式运行链路，系统都应该满足：后端只依赖 Python 运行时，不再要求 Node bridge 或 Node transport 参与。

**验证需求：** 需求 1、需求 5

## 7. 测试策略

### 7.1 单元测试

- Python transport 的登录、状态刷新、轮询、发送和二维码生成
- 旧运行时状态到新内部结构的兼容映射

### 7.2 集成测试

- `config_preview -> action -> runtime_state` 的扫码链路
- `channel.poll` 和 `channel.send` 的标准化链路

### 7.3 端到端测试

- 纯 Python 运行镜像里完成扫码登录、刷新状态、收消息、发文本
- 容器内不安装 Node 仍可完成微信插件主链路

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.1、§3.3、§6.2 | 容器验证、代码检索、回归测试 |
| `requirements.md` 需求 2 | `design.md` §2.3、§3.2、§6.1 | 接口回归、人工走查 |
| `requirements.md` 需求 3 | `design.md` §2.3、§3.3、§4.2 | 单元测试、集成测试 |
| `requirements.md` 需求 4 | `design.md` §4.1、§5.3 | 迁移测试、状态回放 |
| `requirements.md` 需求 5 | `design.md` §1.1、§6.2 | 文档检查、代码检索 |

## 8. 风险与待确认项

### 8.1 风险

- 现有 Node transport 某些协议细节如果没有被完整记录，Python 重写可能出现行为差异
- 旧状态字段虽然能复用，但如果含有 Node 专属假设，迁移阶段容易踩脏数据
- 二维码、媒体和 `context_token` 是最容易出现“表面能跑，边角全坏”的区域

### 8.2 待确认项

- Python 侧二维码生成最终使用哪一个纯 Python 方案，要求可直接输出宿主可渲染结果
- 旧 Node vendor 目录是直接删除，还是保留一段过渡时间但不再参与运行
- 插件开发文档的“后端必须使用 Python”约束，是写入现有开发规范还是新增专门章节
