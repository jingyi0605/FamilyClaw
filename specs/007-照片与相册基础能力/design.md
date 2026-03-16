# 设计文档 - 照片与相册基础能力

状态：Draft

## 1. 概述

### 1.1 目标

- 在当前模块化单体架构上补一条正式的照片主链，不另起一套独立系统。
- 让照片和现有 `conversation`、`memory`、`channel`、`ai_gateway` 真正接上，并只把 `plugin_job` 当异步执行器使用。
- 把“发照片问问题、识别人、沉淀家庭故事和时间线”拆成可分阶段落地的结构。

### 1.2 覆盖需求

- `requirements.md` 需求 1：统一照片资产接入
- `requirements.md` 需求 2：对话中发送照片并触发分析
- `requirements.md` 需求 3：人脸识别与家庭成员关联
- `requirements.md` 需求 4：照片内容分析写回家庭记忆
- `requirements.md` 需求 5：家人圈故事生成
- `requirements.md` 需求 6：照片剧情时间线
- `requirements.md` 需求 7：照片权限、隐私与审计

### 1.3 当前现状判断

当前仓库里已经有几块能直接复用的东西：

- `apps/api-server/app/modules/conversation/`：正式会话主链已经存在，但消息模型还只有文本，没有正式附件层。
- `apps/api-server/app/modules/channel/`：外部通讯通道已经能进正式会话，这给“聊天里收照片”留了入口。
- 现有后台任务链已经存在，适合复用来跑 `Immich` 同步和异步分析，但照片领域规则不能继续塞进任务执行器的语义里。
- `apps/api-server/app/modules/memory/`：已经有 `event_records`、`memory_cards`，可以承接照片记忆、故事结果和时间线事件。
- `apps/api-server/app/modules/ai_gateway/`：`vision` 能力已经是正式 capability，不需要再临时绕路。

现在缺的东西也很明确：

- 没有正式的照片资产表、附件表和人物绑定表。
- 对话主链还不能稳定接住图片输入。
- 照片和家庭成员中心之间没有正式绑定层。
- `Immich` 和现有照片语义层、记忆主链还没接上。

### 1.4 关键设计判断

- 不做独立照片微服务。第一版继续走当前模块化单体，这才符合仓库现状。
- 不把照片原始文件长期存成 OpenClaw 自己的云盘。`Immich` 负责原图、缩略图和基础相册底座。
- 也不走“本项目只透传 `Immich` 接口”的轻飘方案。本项目必须保存正式照片业务索引，不然后面的成员绑定、故事、时间线都会到处漏风。
- 对话图片能力不另造“图片问答接口”，直接扩现有 `conversation` 消息和通道入站模型。
- 异步同步、批量分析和重跑继续复用 `plugin_job`，但它只负责排队和执行；照片领域规则必须落在本项目 `photo` 模块。
- 长期结果优先写进 `memory_cards`，故事、时间线都以记忆和事件为主，不单独做一套难维护的内容库。
- 人脸识别要有 provider 抽象。默认推荐 `Immich` 先跑通，后续可加 `CompreFace` 增强，但“最终这个人是谁”的家庭语义结论归本项目。

### 1.5 混合架构边界

这一版采用混合架构，边界如下：

- `Immich` 负责：
  - 原始照片文件
  - 缩略图和预览图
  - 基础 EXIF / 时间地点元数据
  - 基础相册与人物聚类
- `FamilyClaw` 负责：
  - `photo_assets` 业务主键和家庭归属
  - 会话附件关联
  - 图片分析记录
  - 人脸组和家庭成员绑定结果
  - 照片记忆、故事和时间线
  - 权限、审计、纠错和人工确认

简单说：文件底座放外部，家庭语义放本地。

### 1.6 技术约束

- 后端：`FastAPI + SQLAlchemy + Alembic`
- 前端：`user-web React + TypeScript`
- 数据存储：当前主数据库 + 外部 `Immich` 资产存储；结构变更只能走 `Alembic`
- 异步任务：复用当前 `plugin_job` / worker 链路，但只当任务执行器
- 认证授权：沿用当前 `admin actor / bound member actor`
- 外部依赖：`Immich`、AI Gateway `vision` provider、可选 `CompreFace`

## 2. 架构

### 2.1 系统结构

第一版按下面这条链做，够用，也不乱：

1. 入口层
   - `user-web` 上传照片
   - 通讯通道接收外部图片消息
   - `Immich` 同步任务拉照片元数据和人物聚类
2. 照片接入层
   - 新增 `photo` 模块，负责资产建档、来源追踪、去重、权限级别和外部引用
   - 扩 `conversation` 与 `channel` 的消息模型，支持照片附件
3. 分析编排层
   - 复用 `plugin_job` 做 `Immich` 同步、批量重分析和批量故事生成的异步执行
   - 复用 `ai_gateway` 的 `vision` 能力做图片内容理解
   - 复用可替换的人脸 provider 做人脸识别，但绑定规则由本地 `photo.face_binding_service` 执行
4. 家庭语义层
   - `photo` 模块把照片里的人、事件、地点、摘要写进结构化结果
   - `memory` 模块负责沉淀长期记忆、故事卡和时间线事件
5. 消费层
   - `conversation` 读取照片分析结果参与问答
   - 记忆页、相册页、故事页、时间线页读取正式数据

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `photo.asset_service` | 接照片、建资产、去重、维护来源和状态 | 上传文件、外部资产引用、会话附件 | `photo_assets` |
| `photo.analysis_service` | 触发视觉分析、人脸解析、结果归档 | 照片资产、AI provider、face provider | `photo_analysis_records`、`photo_asset_faces` |
| `photo.face_binding_service` | 把 face group 绑定到家庭成员，并处理纠错 | 人脸组、成员、人工确认 | `photo_face_groups`、`photo_asset_members` |
| `photo.story_service` | 基于照片和记忆生成家庭故事草稿 | 资产集合、事件上下文、成员关系 | `memory_cards`（story） |
| `photo.timeline_service` | 按成员、事件、时间聚合照片时间线 | 查询条件、权限范围 | 时间线视图结果 |
| `conversation` 扩展层 | 让会话消息可以挂照片资产并触发分析 | 用户消息、通道入站图片 | 会话附件、分析任务 |
| `photo.job_service` | 把照片相关同步、重分析、故事生成任务提交给异步执行器 | 照片任务请求 | 任务记录、异步结果 |
| `memory` 写回层 | 把照片事件、故事、成长节点沉淀为长期记忆 | 结构化照片结果 | `event_records`、`memory_cards` |

### 2.3 关键流程

#### 2.3.1 对话上传照片并即时分析

1. `user-web` 或通道入口把图片作为正式附件发到会话消息。
2. `photo.asset_service` 先创建 `photo_asset`，记录来源、哈希、会话来源和外部文件引用。
3. `conversation` 创建用户消息，并把附件关联到消息。
4. 系统立刻回复“已收到，正在分析”，保证体感不死。
5. `photo.analysis_service` 触发视觉分析和人脸检测。
6. 分析结果回写照片资产和会话回复，必要时生成记忆候选或正式记忆。

#### 2.3.2 `Immich` 批量同步照片

1. 管理员配置 `Immich` 连接后，系统通过本地照片任务入口发起异步同步，拉取照片元数据和外部人物信息。
2. 同步任务把每张外部照片转成正式 `photo_asset`，保留 `provider_asset_id` 和相册引用。
3. 同步任务把外部人脸组或人物聚类转成 `photo_face_group` 和 `photo_asset_face`。
4. 已确认的人脸组只在本地映射到家庭成员，未确认的进入待确认列表。
5. 值得沉淀的照片事件写入记忆中心。

#### 2.3.3 人脸组绑定家庭成员

1. 管理员在照片人物管理页看到待确认人脸组。
2. 管理员把该组绑定到某个成员，或标记为忽略/访客。
3. `photo.face_binding_service` 更新人脸组状态，并回填该组关联的照片成员结果。
4. 系统刷新后续问答、照片检索、时间线和故事生成的成员关联结果。
5. 审计日志记录这次绑定和修订。

#### 2.3.4 照片写回家庭记忆

1. `photo.analysis_service` 把照片里的时间、人物、摘要、事件候选整理成结构化结果。
2. `memory` 写回入口先落 `event_records`，记录这次照片事件来源。
3. 去重逻辑判断这是新事件、已有事件补充，还是只更新观察结果。
4. 系统生成或更新 `memory_cards`，并把照片资产引用挂进 `content_json`。
5. 后续问答和时间线直接复用这批正式记忆。

#### 2.3.5 生成家人圈故事

1. 用户选择一组照片或某个时间段触发故事生成。
2. 系统先做权限过滤，再读取对应资产、成员关系和已存在记忆。
3. AI 负责润色叙事，但事实来源以照片元数据和记忆结果为主。
4. 生成结果先保存为故事草稿，再由用户确认是否沉淀为正式故事卡。
5. 正式故事写入 `memory_cards`，并保留关联的照片资产列表。

#### 2.3.6 查询照片剧情时间线

1. 用户按成员、事件、相册或时间范围发起查询。
2. 系统先查可见的 `photo_assets`、照片事件记忆和故事卡。
3. `photo.timeline_service` 以时间为主轴，把照片、事件和故事片段合并排序。
4. 对缺失成员或事件信息的照片，保留“待补充”标记，不强行编造。
5. 返回给前端结构化时间线结果。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7

- `apps/api-server/app/modules/photo/models.py`：照片主数据、人脸组、分析记录和关联关系模型。
- `apps/api-server/app/modules/photo/service.py`：资产接入、去重、状态流转。
- `apps/api-server/app/modules/photo/analysis_service.py`：视觉分析和人脸 provider 编排。
- `apps/api-server/app/modules/photo/face_binding_service.py`：成员绑定与纠错。
- `apps/api-server/app/modules/photo/story_service.py`：故事草稿和写回。
- `apps/api-server/app/modules/photo/timeline_service.py`：时间线查询。
- `apps/api-server/app/api/v1/endpoints/photos.py`：照片相关正式 API。
- `apps/api-server/app/modules/conversation/`：扩消息输入结构，支持附件。
- `apps/api-server/app/modules/channel/`：扩通道入站消息，支持图片事件。
- `apps/api-server/app/modules/photo/provider_clients/immich_sync_service.py`：本地 `Immich` 同步编排服务。
- `apps/api-server/app/modules/photo/jobs.py`：把同步和批量分析任务接到 `plugin_job` 或 worker。

### 3.1.1 动作与定义的正式分工

这部分必须说死，不然后面实现时一定会串味。

#### 交给 `ImmichConnector` / `ImmichSyncPlugin` 的动作

- 鉴权、连接探测、版本探测
- 分页拉取资产列表
- 拉资产详情、EXIF、相册归属、人物聚类
- 增量同步游标推进
- 失败重试、限流处理、超时控制
- 输出标准化同步记录和同步摘要
- 把长任务挂到 `plugin_job` 执行

#### 留在 `photo` 模块里的定义

- `photo_assets` 的业务主键和生命周期
- `photo_face_groups`、`photo_asset_faces`、`photo_asset_members` 的本地语义
- `Immich person -> member` 的最终绑定结论
- 对话附件和照片资产的关联
- 照片分析、人脸纠错、记忆写回、故事、时间线
- 权限、审计、人工确认和隐私规则

#### 明确不允许的做法

- 不允许插件直接写最终 `member_id` 结论
- 不允许插件直接写故事卡、时间线节点或正式记忆
- 不允许业务代码把 `immich_asset_id` 直接当本地主键使用

### 3.2 数据结构

覆盖需求：1、2、3、4、5、6、7

#### 3.2.0 第一批数据表草案

第一批表结构先把“谁、哪张图、和谁有关、同步到哪一步”立住，不急着一口气把所有花活全塞进来。

建议第一批就建下面 8 张表：

1. `photo_provider_accounts`
   - 存 `Immich` 连接配置、启停状态、最近探测结果
2. `photo_sync_cursors`
   - 存每个家庭、每个 provider 的增量同步游标和最近同步摘要
3. `photo_assets`
   - 本地照片业务主表
4. `conversation_message_attachments`
   - 会话消息和照片资产关联表
5. `photo_analysis_records`
   - 视觉分析、故事草稿、人脸分析记录
6. `photo_face_groups`
   - 外部人物组到本地人物组的稳定映射
7. `photo_asset_faces`
   - 单张照片上的具体人脸实例
8. `photo_asset_members`
   - 照片和家庭成员的最终或候选关系

第一批先不强上完整逻辑相册表。`photo_albums` 和 `photo_album_items` 可以在主链稳定后第二批再补。

#### 3.2.0.1 `photo_provider_accounts`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | provider 账号主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键、索引 |
| `provider_type` | `varchar(30)` | 是 | 当前固定 `immich` | 索引 |
| `display_name` | `varchar(100)` | 是 | 页面显示名 | 非空 |
| `base_url` | `varchar(500)` | 是 | `Immich` 服务地址 | 非空 |
| `api_key_secret_ref` | `varchar(255)` | 是 | API Key 的 secret 引用 | 非空 |
| `sync_enabled` | `boolean` | 是 | 是否允许同步 | 默认 true |
| `status` | `varchar(20)` | 是 | `draft` / `active` / `degraded` / `disabled` | 索引 |
| `last_probe_status` | `varchar(20)` | 否 | 最近探测结果 | 可空 |
| `last_error_code` | `varchar(100)` | 否 | 最近错误码 | 可空 |
| `last_error_message` | `text` | 否 | 最近错误信息 | 可空 |
| `last_synced_at` | `text` | 否 | 最近成功同步时间 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.0.2 `photo_sync_cursors`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 游标主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键、索引 |
| `provider_account_id` | `text` | 是 | 对应 provider 账号 | 外键、索引 |
| `sync_scope` | `varchar(30)` | 是 | `all_assets` / `album` / `person` | 索引 |
| `scope_ref` | `varchar(255)` | 否 | 作用域引用，如 album id | 可空 |
| `cursor_value` | `text` | 否 | 增量游标 | 可空 |
| `last_job_id` | `text` | 否 | 最近任务 ID | 可空 |
| `last_status` | `varchar(20)` | 是 | `idle` / `running` / `succeeded` / `failed` | 索引 |
| `last_summary_json` | `text` | 否 | 最近同步摘要 | 可空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.0.3 第一批迁移建议

按当前项目风格，第一批不要做一个巨无霸 migration，建议拆成三步：

- 第一步：`photo_provider_accounts`、`photo_sync_cursors`
- 第二步：`photo_assets`、`conversation_message_attachments`、`photo_analysis_records`
- 第三步：`photo_face_groups`、`photo_asset_faces`、`photo_asset_members`

这样排错最省脑子。

#### 3.2.1 `photo_assets`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 照片资产主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键、索引 |
| `source_type` | `varchar(30)` | 是 | `upload` / `channel` / `immich_sync` | 索引 |
| `source_ref` | `varchar(255)` | 否 | 来源对象 ID，如消息 ID、外部资产 ID | 可空 |
| `provider_type` | `varchar(30)` | 是 | `immich` / `local_upload` / `channel_cache` | 索引 |
| `provider_asset_id` | `varchar(255)` | 否 | 外部资产 ID | 可空、索引 |
| `storage_path` | `text` | 否 | 本地暂存或缓存路径 | 可空 |
| `sha256` | `varchar(64)` | 否 | 文件摘要 | 家庭内唯一索引候选 |
| `mime_type` | `varchar(100)` | 是 | 文件类型 | 非空 |
| `width` | `int` | 否 | 宽度 | 可空 |
| `height` | `int` | 否 | 高度 | 可空 |
| `captured_at` | `text` | 否 | 拍摄时间 | 可空、索引 |
| `timezone` | `varchar(64)` | 否 | 拍摄时区 | 可空 |
| `location_text` | `varchar(255)` | 否 | 地点文本 | 可空 |
| `privacy_level` | `varchar(20)` | 是 | `public` / `family` / `private` / `sensitive` | 索引 |
| `status` | `varchar(20)` | 是 | `pending` / `ready` / `failed` / `deleted` | 索引 |
| `analysis_status` | `varchar(20)` | 是 | `pending` / `running` / `completed` / `failed` / `degraded` | 索引 |
| `latest_analysis_id` | `text` | 否 | 最新分析记录 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.2 `conversation_message_attachments`

这张表不属于 `photo` 模块独占，但照片能力第一版必须补上。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 附件主键 | 主键 |
| `message_id` | `text` | 是 | 所属会话消息 | 外键、索引 |
| `attachment_type` | `varchar(20)` | 是 | `photo` / `file` | 索引 |
| `photo_asset_id` | `text` | 否 | 对应照片资产 | 外键、索引 |
| `file_name` | `varchar(255)` | 否 | 原始文件名 | 可空 |
| `mime_type` | `varchar(100)` | 是 | 文件类型 | 非空 |
| `sort_order` | `int` | 是 | 顺序 | 默认 0 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |

#### 3.2.3 `photo_analysis_records`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 分析记录主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键、索引 |
| `photo_asset_id` | `text` | 是 | 照片资产 | 外键、索引 |
| `analysis_type` | `varchar(30)` | 是 | `vision_summary` / `face_detection` / `story_draft` | 索引 |
| `provider_type` | `varchar(30)` | 是 | `ai_gateway` / `immich` / `compreface` | 索引 |
| `provider_ref` | `varchar(255)` | 否 | 外部调用引用 | 可空 |
| `status` | `varchar(20)` | 是 | `pending` / `running` / `completed` / `failed` / `degraded` | 索引 |
| `summary_text` | `text` | 否 | 人类可读摘要 | 可空 |
| `result_json` | `text` | 否 | 结构化结果 | 可空 |
| `error_code` | `varchar(100)` | 否 | 错误码 | 可空 |
| `error_message` | `text` | 否 | 错误信息 | 可空 |
| `started_at` | `text` | 否 | 开始时间 | 可空 |
| `finished_at` | `text` | 否 | 完成时间 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |

#### 3.2.4 `photo_face_groups`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 人脸组主键 | 主键 |
| `household_id` | `text` | 是 | 所属家庭 | 外键、索引 |
| `provider_type` | `varchar(30)` | 是 | `immich` / `compreface` | 索引 |
| `provider_group_ref` | `varchar(255)` | 是 | 外部人物或人脸组 ID | 家庭+provider 唯一 |
| `member_id` | `text` | 否 | 已绑定家庭成员 | 外键、索引 |
| `display_name` | `varchar(100)` | 否 | 外部或人工显示名 | 可空 |
| `binding_status` | `varchar(20)` | 是 | `unmatched` / `pending_review` / `matched` / `ignored` | 索引 |
| `confidence` | `real` | 否 | 当前绑定置信度 | 可空 |
| `sample_photo_asset_id` | `text` | 否 | 代表照片 | 可空 |
| `last_seen_at` | `text` | 否 | 最近出现时间 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.5 `photo_asset_faces`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 单次人脸实例主键 | 主键 |
| `photo_asset_id` | `text` | 是 | 所属照片 | 外键、索引 |
| `face_group_id` | `text` | 否 | 所属人脸组 | 外键、索引 |
| `provider_face_ref` | `varchar(255)` | 否 | 外部人脸实例 ID | 可空 |
| `bbox_json` | `text` | 否 | 人脸框坐标 | 可空 |
| `confidence` | `real` | 否 | 识别置信度 | 可空 |
| `match_status` | `varchar(20)` | 是 | `detected` / `matched` / `candidate` / `ignored` | 索引 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |

#### 3.2.6 `photo_asset_members`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `photo_asset_id` | `text` | 是 | 照片资产 | 联合主键 |
| `member_id` | `text` | 是 | 家庭成员 | 联合主键 |
| `relation_role` | `varchar(30)` | 是 | `recognized` / `candidate` / `subject` / `uploader` | 联合主键 |
| `confidence` | `real` | 否 | 关联置信度 | 可空 |
| `source` | `varchar(30)` | 是 | `face_group` / `manual` / `import` | 非空 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |

#### 3.2.7 `photo_albums` 与 `photo_album_items`

第一版只做基础集合能力，别先做复杂相册系统。

`photo_albums`：保存家庭内逻辑相册，如“2025 春节”“朵朵成长相册”“家人圈精选”。

`photo_album_items`：保存相册和照片资产的关联顺序与来源。

#### 3.2.8 与 `memory_cards` 的关系约定

照片故事和时间线不单独再造内容库，第一版统一这样做：

- 照片事件记忆：`memory_type=event`
- 成长节点记忆：`memory_type=growth`
- 照片故事：`memory_type=event` 或 `memory_type=growth`，并在 `content_json` 标记 `content_kind=photo_story`
- 时间线展示：查询 `photo_assets + event_records + memory_cards` 聚合生成，不新建 `photo_timelines` 主表

### 3.3 接口契约

覆盖需求：1、2、3、4、5、6、7

#### 3.3.1 照片上传接口

- 类型：HTTP
- 路径：`POST /api/v1/photos/uploads`
- 输入：`multipart/form-data`，包含照片文件、`household_id`、可选 `conversation_session_id`、`privacy_level`
- 输出：`photo_asset` 基础信息、分析受理状态
- 校验：文件大小、MIME 类型、家庭权限、隐私级别
- 错误：文件不合法、无权限、上传失败、存储失败

#### 3.3.2 照片列表与详情接口

- 类型：HTTP
- 路径：
  - `GET /api/v1/photos/assets`
  - `GET /api/v1/photos/assets/{asset_id}`
- 输入：家庭、成员、时间范围、相册、状态、查询词
- 输出：照片资产列表、详情、分析摘要、成员关联
- 校验：严格走照片权限和成员权限过滤
- 错误：无权限、资产不存在、查询参数非法

#### 3.3.3 人脸组绑定接口

- 类型：HTTP
- 路径：
  - `GET /api/v1/photos/face-groups`
  - `POST /api/v1/photos/face-groups/{group_id}/bind-member`
  - `POST /api/v1/photos/face-groups/{group_id}/ignore`
- 输入：人脸组 ID、成员 ID、绑定理由或纠错说明
- 输出：绑定后的人脸组详情和受影响资产数量
- 校验：只允许管理员或授权成员执行
- 错误：人脸组不存在、成员不存在、跨家庭绑定、冲突绑定

#### 3.3.4 手动重跑图片分析接口

- 类型：HTTP
- 路径：`POST /api/v1/photos/assets/{asset_id}/analyze`
- 输入：分析类型、是否强制重跑
- 输出：创建的异步任务信息
- 校验：资产可访问、分析 provider 已配置
- 错误：能力不可用、资产不存在、任务重复

#### 3.3.5 照片故事生成接口

- 类型：HTTP
- 路径：`POST /api/v1/photos/stories/generate`
- 输入：资产 ID 列表、故事类型、时间范围、主角成员、是否直接写回记忆
- 输出：故事草稿、关联照片、生成状态
- 校验：权限、敏感内容过滤、数量上限
- 错误：素材不足、权限不够、生成失败

#### 3.3.6 照片时间线接口

- 类型：HTTP
- 路径：`GET /api/v1/photos/timeline`
- 输入：家庭 ID、成员 ID、事件类型、起止时间、相册 ID
- 输出：按时间排序的照片事件节点
- 校验：时间范围和权限范围
- 错误：无权限、参数非法

#### 3.3.7 `Immich` 同步接口

- 类型：HTTP + Async Job
- 路径：
  - `POST /api/v1/photos/providers/immich/sync`
  - `GET /api/v1/plugin-jobs/{job_id}`（沿用现有任务状态查询接口）
- 输入：家庭 ID、同步范围、相册或时间窗口
- 输出：同步任务受理结果
- 校验：管理员权限、provider 配置完整
- 错误：provider 未配置、网络失败、鉴权失败

#### 3.3.7.1 `ImmichConnector` 输入 schema 草案

插件输入只负责动作，不带业务结论。

```json
{
  "provider_account_id": "photo-provider-001",
  "sync_mode": "incremental",
  "scope": {
    "scope_type": "album",
    "scope_ref": "album_123"
  },
  "cursor": "2026-03-15T08:00:00Z",
  "page_size": 200,
  "include_people": true,
  "include_albums": true,
  "force": false,
  "request_id": "photo-sync-req-001"
}
```

字段建议：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `provider_account_id` | `string` | 是 | 对应本地 `photo_provider_accounts.id` |
| `sync_mode` | `string` | 是 | `full` / `incremental` / `asset` / `album` |
| `scope.scope_type` | `string` | 否 | `all` / `album` / `asset` / `person` |
| `scope.scope_ref` | `string` | 否 | 具体 album id、asset id、person id |
| `cursor` | `string` | 否 | 增量同步游标 |
| `page_size` | `number` | 否 | 单次分页大小，默认 200 |
| `include_people` | `boolean` | 否 | 是否同步人物聚类 |
| `include_albums` | `boolean` | 否 | 是否同步相册归属 |
| `force` | `boolean` | 否 | 是否忽略部分缓存直接强制同步 |
| `request_id` | `string` | 否 | 调试和追踪用请求 ID |

#### 3.3.7.2 `ImmichConnector` 输出 schema 草案

插件输出只返回标准化记录、摘要和游标，不返回最终业务结论。

```json
{
  "records": [
    {
      "record_type": "photo_asset",
      "provider_type": "immich",
      "provider_asset_id": "asset_001",
      "captured_at": "2026-03-15T06:30:00Z",
      "mime_type": "image/jpeg",
      "width": 4032,
      "height": 3024,
      "checksum": "sha256:xxxx",
      "album_refs": ["album_123"],
      "people": [
        {
          "provider_group_ref": "person_001",
          "provider_face_ref": "face_001",
          "confidence": 0.98,
          "bbox": {"left": 0.1, "top": 0.2, "width": 0.3, "height": 0.4}
        }
      ],
      "metadata": {
        "location_text": "Shanghai",
        "timezone": "Asia/Shanghai"
      }
    }
  ],
  "sync_summary": {
    "fetched": 120,
    "created": 30,
    "updated": 80,
    "skipped": 8,
    "failed": 2
  },
  "next_cursor": "2026-03-15T09:00:00Z",
  "warnings": [],
  "errors": []
}
```

字段建议：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `records` | `array` | 是 | 标准化同步记录列表 |
| `records[].record_type` | `string` | 是 | 当前先固定 `photo_asset` |
| `records[].provider_type` | `string` | 是 | 当前固定 `immich` |
| `records[].provider_asset_id` | `string` | 是 | `Immich` 资产 ID |
| `records[].captured_at` | `string` | 否 | 拍摄时间 |
| `records[].mime_type` | `string` | 是 | 文件类型 |
| `records[].width` | `number` | 否 | 宽度 |
| `records[].height` | `number` | 否 | 高度 |
| `records[].checksum` | `string` | 否 | 内容摘要 |
| `records[].album_refs` | `array[string]` | 否 | 相册引用 |
| `records[].people` | `array` | 否 | 人物聚类和人脸实例 |
| `records[].people[].provider_group_ref` | `string` | 是 | 外部人物组 ID |
| `records[].people[].provider_face_ref` | `string` | 否 | 外部人脸实例 ID |
| `records[].people[].confidence` | `number` | 否 | 识别置信度 |
| `records[].people[].bbox` | `object` | 否 | 人脸框坐标 |
| `records[].metadata` | `object` | 否 | 扩展元数据 |
| `sync_summary` | `object` | 是 | 同步摘要 |
| `next_cursor` | `string` | 否 | 下次增量同步游标 |
| `warnings` | `array` | 否 | 非致命警告 |
| `errors` | `array` | 否 | 致命或局部失败列表 |

#### 3.3.7.3 `ImmichConnector` 明确不返回的字段

插件输出里不允许出现这些字段：

- `member_id`
- `memory_card_id`
- `story_id`
- `timeline_id`
- `final_privacy_level`

这些都属于本地 `photo` 领域定义，不属于插件动作层。

#### 3.3.8 会话消息附件扩展

- 类型：HTTP / Channel / Function
- 标识：扩展 `conversation` 创建 turn 的输入模型
- 输入：文本 + 附件列表，其中附件类型至少支持 `photo`
- 输出：正式消息 + 附件关联 + 异步分析状态
- 校验：附件数量、文件类型、会话权限
- 错误：附件不支持、会话不存在、上传失败

### 3.4 建议文件结构

- `apps/api-server/app/modules/photo/models.py`
- `apps/api-server/app/modules/photo/repository.py`
- `apps/api-server/app/modules/photo/schemas.py`
- `apps/api-server/app/modules/photo/service.py`
- `apps/api-server/app/modules/photo/analysis_service.py`
- `apps/api-server/app/modules/photo/face_binding_service.py`
- `apps/api-server/app/modules/photo/story_service.py`
- `apps/api-server/app/modules/photo/timeline_service.py`
- `apps/api-server/app/modules/photo/provider_clients/immich.py`
- `apps/api-server/app/modules/photo/provider_clients/compreface.py`
- `apps/api-server/app/modules/photo/provider_clients/immich_sync_service.py`
- `apps/api-server/app/modules/photo/jobs.py`
- `apps/api-server/app/api/v1/endpoints/photos.py`
- `apps/user-web/src/pages/PhotosPage.tsx`
- `apps/user-web/src/components/PhotoFaceBindingPanel.tsx`
- `apps/user-web/src/components/PhotoStoryComposer.tsx`

## 4. 数据与状态模型

### 4.1 数据关系

- 一个家庭有很多 `photo_assets`。
- 一张 `photo_asset` 可以来自上传、聊天通道或 `Immich` 同步。
- 每张 `photo_asset` 在本项目内都有稳定业务主键，不能只靠 `Immich asset id` 直接代替。
- 一张 `photo_asset` 可以对应多个 `photo_analysis_records`。
- 一个 `photo_face_group` 可以绑定零个或一个家庭成员。
- 一张照片可以出现多个 `photo_asset_faces`，最终映射成零个或多个 `photo_asset_members`。
- 一张照片可以进入多个逻辑相册。
- 一张照片可以触发事件记忆、成长记忆或故事卡，但这些长期内容统一落在 `memory_cards`。

### 4.2 状态流转

#### 4.2.1 照片资产状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `pending` | 资产刚建档，文件或元数据还没完整 | 刚上传或刚同步 | 文件可用后进入 `ready`，失败进入 `failed` |
| `ready` | 资产可读可分析 | 接入完成 | 删除进入 `deleted` |
| `failed` | 资产接入失败 | 文件拉取、去重或落库失败 | 重试成功可回 `ready` |
| `deleted` | 逻辑删除 | 用户删除或权限收回 | 终态 |

#### 4.2.2 分析状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `pending` | 待分析 | 资产刚创建 | 开始执行进入 `running` |
| `running` | 正在分析 | 已创建分析任务 | 完成、失败或降级 |
| `completed` | 分析完成 | 成功得到结果 | 新一轮重跑可回 `running` |
| `failed` | 分析失败 | 外部依赖失败或结果非法 | 重试后可回 `running` |
| `degraded` | 有部分结果，但不完整 | 只拿到部分识别结果 | 补跑后可回 `running` 或 `completed` |

#### 4.2.3 人脸组绑定状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `unmatched` | 还没匹配家庭成员 | 同步或识别后首次创建 | 人工或自动候选进入 `pending_review` / `matched` |
| `pending_review` | 系统有候选，但不够稳 | 低置信度或冲突 | 人工确认后进入 `matched` 或 `ignored` |
| `matched` | 已正式绑定成员 | 人工确认或高置信规则通过 | 纠错后可重新回 `pending_review` |
| `ignored` | 明确忽略 | 管理员标记访客或无关对象 | 可手动恢复 |

## 5. 错误处理

### 5.1 错误类型

- `photo_asset_invalid_file`：图片格式、大小或内容不合法。
- `photo_asset_not_found`：照片资产不存在或不属于当前家庭。
- `photo_provider_unavailable`：`Immich`、人脸服务或视觉 provider 不可用。
- `photo_analysis_failed`：图片分析执行失败。
- `photo_face_binding_conflict`：同一人脸组绑定冲突。
- `photo_privacy_forbidden`：当前成员无权查看或处理该照片。

### 5.2 错误响应格式

```json
{
  "detail": "当前照片没有访问权限",
  "error_code": "photo_privacy_forbidden",
  "field": null,
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误
   - 直接拒绝，不创建半成资产。
2. 外部 provider 失败
   - 保留 `photo_asset` 主记录，把分析状态记成 `failed` 或 `degraded`。
3. 低置信度识别
   - 不自动写确定成员，只给候选结果和待确认状态。
4. 记忆写回失败
   - 不影响照片资产存在，保留事件和失败原因，允许重跑。
5. 权限失败
   - 返回 `403`，同时记录审计日志。

## 6. 正确性属性

### 6.1 属性 1：同一照片不会被重复建成多条正式资产

*对于任何* 同一家庭内内容相同或 provider 引用相同的照片输入，系统都应该满足：最多只存在一条活跃的正式照片资产记录。

**验证需求：** 需求 1

### 6.2 属性 2：低置信度人脸结果不能冒充正式成员事实

*对于任何* 未达到确认阈值或存在冲突的人脸识别结果，系统都应该满足：不能直接把该结果写成确定成员绑定或高可信记忆事实。

**验证需求：** 需求 3、需求 7

### 6.3 属性 3：照片故事不能脱离事实来源单独漂浮

*对于任何* 照片故事或时间线内容，系统都应该满足：都能追溯到至少一张正式照片资产和对应的分析/记忆来源。

**验证需求：** 需求 4、需求 5、需求 6

### 6.4 属性 4：图片分析失败不能拖垮对话主链

*对于任何* 会话中的图片分析失败或外部依赖超时，系统都应该满足：会话仍然可继续，用户能收到清楚的降级反馈。

**验证需求：** 需求 2、非功能需求 2

## 7. 测试策略

### 7.1 单元测试

- 照片去重键与来源归一化
- 人脸组状态流转与成员绑定冲突
- 照片权限过滤
- 时间线聚合排序

### 7.2 集成测试

- 上传照片 -> 建资产 -> 跑分析 -> 回写会话
- `Immich` 同步 -> 生成人脸组 -> 本地绑定成员 -> 产出照片成员关联
- 照片分析 -> 事件写回 -> `memory_cards`
- 故事生成 -> 草稿 -> 正式记忆写回

### 7.3 端到端测试

- `user-web` 上传照片并在对话里得到结果
- 通讯通道发送图片并得到文字回复
- 管理员确认人物绑定并在相册页看到更新
- 生成一条家人圈故事和一条时间线查询结果

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§2.3.2、§3.2.1 | 上传测试、同步测试、去重测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.1、§3.3.8、§6.4 | 对话集成测试、降级测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§3.2.4、§4.2 | 绑定测试、冲突测试、审计测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.4、§3.2.8、§6.3 | 记忆写回测试、事件去重测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.5、§3.3.5、§6.3 | 故事生成测试、权限测试 |
| `requirements.md` 需求 6 | `design.md` §2.3.6、§4.1 | 时间线查询测试、排序测试 |
| `requirements.md` 需求 7 | `design.md` §5.1、§5.3、§6.2 | 权限测试、隐私测试、审计测试 |

## 8. 风险与待确认项

### 8.1 风险

- 如果会话附件层设计太随意，后面视频、语音、文件都会继续返工。
- 如果把人物识别结论写得太激进，很容易把家庭关系数据写脏。
- 如果故事生成不严格复用照片事实和记忆事实，最后只会变成漂亮废话。
- `Immich` 和视觉模型都可能慢，主链必须从一开始就考虑异步和降级。
- 如果本地照片业务索引设计得太薄，后面故事、时间线和权限审计都会被外部接口牵着鼻子走。

### 8.2 待确认项

- 第一版 `user-web` 是否需要单独的相册页面，还是先挂在记忆页/家庭页入口下。
- 是否在第一版就接 `CompreFace`，还是先用 `Immich` 跑通人物识别与绑定主链。
- 聊天通道中的图片是否全部镜像进 `Immich`，还是先允许“只建本地资产，不进外部相册”的模式。
