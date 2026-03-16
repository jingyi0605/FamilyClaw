# 任务清单 - 照片与相册基础能力（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单是给后续实现的人直接开工用的。

你打开任意一个任务，应该马上知道：

- 这一步具体建什么
- 做完以后系统里能看到什么结果
- 依赖什么现有模块
- 主要改哪些文件
- 这一步故意先不做什么
- 做完以后怎么验证

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

## 阶段 1：先把照片主数据和接入主链立住

- [ ] 1.1 建 provider 账号表、同步游标表和照片主表
  - 状态：TODO
  - 这一步到底做什么：先把 `photo_provider_accounts`、`photo_sync_cursors`、`photo_assets` 建出来，让“连哪个 Immich、同步到哪、照片本地主键是什么”这几个底层问题先有正式落点。
  - 做完你能看到什么：数据库里先有 provider 配置、同步进度和照片主表，后面同步和分析不用再靠临时字段硬顶。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 7
    - `design.md` §3.2「数据结构」
    - `design.md` §3.2.0「第一批数据表草案」
    - `design.md` §4.1「数据关系」
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/models.py`
    - `apps/api-server/app/db/models.py`
    - `apps/api-server/migrations/versions/`
  - 这一步先不做什么：先不做人脸实例表、会话附件表，也不做前端页面。
  - 怎么算完成：
    1. `Immich` 连接配置和增量游标有正式表结构
    2. 照片主表有稳定本地主键和外部资产映射字段
    3. 迁移脚本和 model 一致
  - 怎么验证：
    - 跑 `alembic upgrade head`
    - 对照 `design.md` 逐项检查字段和约束
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 7
  - 对应设计：`design.md` §3.2.0、§3.2.0.1、§3.2.0.2、§4.1

- [ ] 1.2 建分析、人脸和会话附件表
  - 状态：TODO
  - 这一步到底做什么：把 `photo_analysis_records`、`photo_face_groups`、`photo_asset_faces`、`photo_asset_members`、`conversation_message_attachments` 补齐，并把表间引用关系收好。
  - 做完你能看到什么：系统里正式有地方存分析结果、人脸结果、成员候选和会话附件。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 7
    - `design.md` §3.2「数据结构」
    - `design.md` §3.2.0.3「第一批迁移建议」
    - `design.md` §4.2「状态流转」
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/models.py`
    - `apps/api-server/app/db/models.py`
    - `apps/api-server/app/modules/conversation/models.py`
    - `apps/api-server/migrations/versions/`
  - 这一步先不做什么：先不接故事和时间线表。
  - 怎么算完成：
    1. 分析、人脸、成员和附件关系能完整表达第一批主链
    2. 迁移脚本和 model 一致
  - 怎么验证：
    - 跑 `alembic upgrade head`
    - 对照 `design.md` 逐项检查字段和约束
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 7
  - 对应设计：`design.md` §3.2.2、§3.2.3、§3.2.4、§3.2.5、§3.2.6、§4.2

- [ ] 1.3 建照片资产 service、去重规则和基础 API
  - 状态：TODO
  - 这一步到底做什么：把上传、建资产、去重、查询详情、状态流转这些逻辑收口到正式 service 和 API。
  - 做完你能看到什么：系统已经能把一张照片正式接进来并查到，不再只是临时文件。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 7
    - `design.md` §2.3.1
    - `design.md` §3.3.1、§3.3.2
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/service.py`
    - `apps/api-server/app/modules/photo/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不跑视觉分析和人脸识别。
  - 怎么算完成：
    1. 能上传或登记一张照片资产
    2. 同图重复导入会被稳定收敛
    3. 能按家庭和基础条件查询资产
  - 怎么验证：
    - API 测试
    - 去重测试
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §2.3.1、§3.3.1、§3.3.2、§6.1

- [ ] 1.4 扩会话与通道输入，支持照片附件
  - 状态：TODO
  - 这一步到底做什么：扩 `conversation` 和 `channel` 的输入模型，让网页和通讯通道都能把照片作为正式附件进入会话。
  - 做完你能看到什么：用户可以在正式对话主链里发照片，而不是另外走一条专用接口。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.1
    - `design.md` §3.3.8
    - `specs/010-通讯通道插件与多平台机器人接入/design.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/app/modules/channel/`
    - `apps/api-server/app/api/v1/endpoints/conversations.py`
    - `apps/user-web/src/pages/ConversationPageV2.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 这一步先不做什么：先不做图片富媒体排版，也不做视频和文件通用上传器。
  - 怎么算完成：
    1. `user-web` 能发送带照片的会话消息
    2. 通讯通道 schema 能表达图片入站
    3. 会话消息能查到附件关联
  - 怎么验证：
    - 前后端联调
    - 通道入站集成测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.1、§3.3.8、§6.4

- [ ] 1.5 阶段检查：照片已经有正式入口了吗
  - 状态：TODO
  - 这一步到底做什么：只检查照片资产、会话附件和基础 API 是不是真的站稳，不往识别和故事乱扩。
  - 做完你能看到什么：照片已经成为系统正式数据，不再是附件黑洞。
  - 先依赖什么：1.1、1.2、1.3、1.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不接 `Immich`，不做故事生成。
  - 怎么算完成：
    1. 照片主数据和会话附件已形成稳定主链
    2. 基础查询和权限过滤能验证
  - 怎么验证：
    - 人工走查
    - API 与会话集成测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 7
  - 对应设计：`design.md` §2.3.1、§3.2、§3.3、§6.1、§6.4

## 阶段 2：把动作接到插件，把定义留在 `photo` 模块

- [ ] 2.1 接 AI Gateway 视觉分析与照片分析记录
  - 状态：TODO
  - 这一步到底做什么：把 `vision` capability 接到照片资产上，产出分析记录、摘要和结构化结果。
  - 做完你能看到什么：系统已经能说出照片里大概是什么，而不是只知道“有一张图”。
  - 先依赖什么：1.5
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` §2.3.1、§2.3.4
    - `design.md` §3.2.3
    - `apps/api-server/app/modules/ai_gateway/`
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/analysis_service.py`
    - `apps/api-server/app/modules/photo/service.py`
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做故事润色，只做基础视觉理解。
  - 怎么算完成：
    1. 单张照片能产出正式分析记录
    2. 会话能看到分析摘要或降级提示
    3. 失败和超时会写明原因
  - 怎么验证：
    - 集成测试
    - provider 降级测试
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.1、§2.3.4、§3.2.3、§6.4

- [ ] 2.2 建 `photo.provider_clients.immich` 和 provider 账号管理逻辑
  - 状态：TODO
  - 这一步到底做什么：先把 `Immich API` 客户端、本地 provider 账号校验、连接探测和配置读写逻辑做扎实，为后面同步动作和本地定义分层打底。
  - 做完你能看到什么：系统已经能稳定保存 `Immich` 连接配置并完成探测，不再靠临时脚本直连外部服务。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 7
    - `design.md` §1.5「混合架构边界」
    - `design.md` §3.2.0.1「photo_provider_accounts」
    - `design.md` §3.1.1「动作与定义的正式分工」
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/provider_clients/immich.py`
    - `apps/api-server/app/modules/photo/service.py`
    - `apps/api-server/app/modules/photo/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不拉全量照片，不跑后台同步。
  - 怎么算完成：
    1. 能创建和更新 `Immich` provider 账号
    2. 能做一次连接探测并保存状态
    3. API 客户端错误会映射成统一错误码
  - 怎么验证：
    - provider API 测试
    - 连接探测测试
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §1.5、§3.1.1、§3.2.0.1、§3.3.7

- [ ] 2.3 建 `ImmichConnector` 插件 manifest 和输入输出契约
  - 状态：TODO
  - 这一步到底做什么：把 `ImmichConnector` 作为插件动作层接进现有插件系统，明确 manifest、entrypoint、输入输出 schema 和错误摘要格式。
  - 做完你能看到什么：插件只负责“连、拉、跑”，不会再混进本地照片语义。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3
    - `design.md` §3.1.1「动作与定义的正式分工」
    - `design.md` §3.3.7.1、§3.3.7.2、§3.3.7.3
    - `specs/004.2-插件系统与外部能力接入/design.md`
    - `apps/api-server/app/modules/plugin/schemas.py`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/immich_connector/manifest.json`
    - `apps/api-server/app/plugins/builtin/immich_connector/`
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不让插件直接落本地业务表。
  - 怎么算完成：
    1. 插件 manifest 能表达 `ImmichConnector` 的动作能力
    2. 输入输出 schema 能过校验
    3. 插件输出不包含 `member_id` 这类本地业务结论
  - 怎么验证：
    - manifest 校验测试
    - 插件输出 schema 测试
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` §3.1.1、§3.3.7.1、§3.3.7.2、§3.3.7.3

- [ ] 2.4 建 `photo.job_service`，只负责把动作提交给 `plugin_job`
  - 状态：TODO
  - 这一步到底做什么：在 `photo` 模块里补正式的 job service，把同步、重抓、重分析这些动作提交给 `plugin_job`，但不把照片语义下沉到插件层。
  - 做完你能看到什么：照片域有自己的任务入口，但执行还是走现有异步框架。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4
    - `design.md` §2.1「系统结构」
    - `design.md` §3.1.1「动作与定义的正式分工」
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/job_service.py`
    - `apps/api-server/app/modules/photo/provider_clients/immich_sync_service.py`
    - `apps/api-server/app/modules/photo/jobs.py`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做本地同步落库。
  - 怎么算完成：
    1. 能创建 `Immich` 同步任务
    2. 能创建单资产重抓或重分析任务
    3. 任务状态可以通过现有 `plugin_job` 查询接口查看
  - 怎么验证：
    - job service 测试
    - API 触发任务测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` §2.1、§3.1.1、§3.3.7

- [ ] 2.5 建 `photo.sync_service`，把插件输出回填本地索引
  - 状态：TODO
  - 这一步到底做什么：消费 `ImmichConnector` 的标准化输出，把外部照片和人物数据同步成正式照片资产和本地人物索引。
  - 做完你能看到什么：外部动作已经正式落成本地定义，而不是停留在任务输出里。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4
    - `design.md` §2.3.2
    - `design.md` §3.1.1「动作与定义的正式分工」
    - `design.md` §3.3.7.2「ImmichConnector 输出 schema 草案」
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/sync_service.py`
    - `apps/api-server/app/modules/photo/repository.py`
    - `apps/api-server/app/modules/photo/service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做成员最终绑定，只落人物组和候选关系。
  - 怎么算完成：
    1. 同步结果能落成本地照片资产
    2. 人物聚类能落成人脸组和人脸实例
    3. 增量游标和同步摘要会更新
  - 怎么验证：
    - 同步回填集成测试
    - 游标推进测试
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` §2.3.2、§3.2.0.2、§3.3.7.2、§4.1

- [ ] 2.6 建照片事件写回记忆主链
  - 状态：TODO
  - 这一步到底做什么：把照片分析结果写入 `event_records` 和 `memory_cards`，形成正式照片记忆。
  - 做完你能看到什么：照片不再只停留在相册层，已经进入家庭记忆层。
  - 先依赖什么：2.1、2.5
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.3.4
    - `design.md` §3.2.8
    - `specs/003-家庭记忆中心/design.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/service.py`
    - `apps/api-server/app/modules/memory/service.py`
    - `apps/api-server/app/modules/memory/query_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做完整故事卡，只把事件和成长记忆打通。
  - 怎么算完成：
    1. 照片可生成事件记录
    2. 重要照片可生成或更新记忆卡
    3. 重复照片不会制造重复记忆
  - 怎么验证：
    - 记忆写回集成测试
    - 去重测试
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §2.3.4、§3.2.8、§6.3

- [ ] 2.7 阶段检查：动作和定义是不是已经分开落地
  - 状态：TODO
  - 这一步到底做什么：检查“插件负责连、拉、跑；photo 负责存、认、管”这条边界是不是在代码里真的站住了。
  - 做完你能看到什么：后续继续做成员绑定和故事时，不会再把业务语义塞回执行器里。
  - 先依赖什么：2.1、2.2、2.3、2.4、2.5、2.6
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩故事生成和时间线 UI。
  - 怎么算完成：
    1. 至少一条上传分析链可验证
    2. 至少一条 `Immich` 同步并回填本地索引的链可验证
    3. 插件输出里没有本地业务结论字段
  - 怎么验证：
    - 集成测试
    - 人工回放主链
    - 契约走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.1.1、§3.3.7.3、§6.1、§6.4

## 阶段 3：把人脸和家庭成员绑定起来

- [ ] 3.1 建人脸组绑定 service 和纠错链路
  - 状态：TODO
  - 这一步到底做什么：把待确认人物、正式绑定、忽略、纠错这些操作收口成统一 service。
  - 做完你能看到什么：照片里的人终于能和家庭成员中心稳定对上。
  - 先依赖什么：2.7
  - 开始前先看：
    - `requirements.md` 需求 3、需求 7
    - `design.md` §2.3.3
    - `design.md` §4.2
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/face_binding_service.py`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/app/modules/audit/service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做全自动高风险绑定。
  - 怎么算完成：
    1. 管理员可以确认、改绑、忽略人脸组
    2. 相关照片成员关联会回填更新
    3. 审计日志完整可查
  - 怎么验证：
    - 绑定 API 测试
    - 冲突与纠错测试
  - 对应需求：`requirements.md` 需求 3、需求 7
  - 对应设计：`design.md` §2.3.3、§4.2、§5.3、§6.2

- [ ] 3.2 把成员绑定结果接进问答和照片查询
  - 状态：TODO
  - 这一步到底做什么：让“找朵朵上个月的照片”“谁和爷爷一起出现过”这类查询用上正式成员绑定结果。
  - 做完你能看到什么：成员视角的照片查询开始真正可用。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 6
    - `design.md` §2.3.6
    - `apps/api-server/app/modules/family_qa/`
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/timeline_service.py`
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做自然语言多轮相册浏览体验。
  - 怎么算完成：
    1. 能按成员筛照片和时间线
    2. 相关问答能引用正式照片结果
  - 怎么验证：
    - 查询测试
    - 问答集成测试
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 6
  - 对应设计：`design.md` §2.3.6、§4.1、§6.2

- [ ] 3.3 阶段检查：系统已经真正认识家里的人了吗
  - 状态：TODO
  - 这一步到底做什么：检查“识别人 -> 绑定成员 -> 反映到照片查询和记忆”这条链是不是闭合。
  - 做完你能看到什么：照片主链开始具备家庭语义，而不只是通用图片理解。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩前端复杂相册工作台。
  - 怎么算完成：
    1. 至少一名成员的人脸绑定链可完整验证
    2. 照片查询和记忆会反映最新绑定结果
  - 怎么验证：
    - 集成测试
    - 人工回放绑定流程
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 7
  - 对应设计：`design.md` §2.3.3、§4.2、§6.2

## 阶段 4：补故事、时间线和用户可见入口

- [ ] 4.1 建家人圈故事生成与草稿确认
  - 状态：TODO
  - 这一步到底做什么：把一组照片生成为家庭内故事草稿，并支持确认后写回正式记忆。
  - 做完你能看到什么：照片不只是能搜，还能产出可读、可存的家庭故事。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` §2.3.5
    - `design.md` §3.3.5
  - 主要改哪里：
    - `apps/api-server/app/modules/photo/story_service.py`
    - `apps/api-server/app/api/v1/endpoints/photos.py`
    - `apps/api-server/app/modules/memory/service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做公开社交分享，也不做复杂模板市场。
  - 怎么算完成：
    1. 用户能生成故事草稿
    2. 故事可追溯到照片和记忆来源
    3. 敏感照片会做权限与脱敏判断
  - 怎么验证：
    - 故事生成集成测试
    - 权限测试
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` §2.3.5、§3.3.5、§6.3

- [ ] 4.2 建照片时间线查询和基础前端页面
  - 状态：TODO
  - 这一步到底做什么：给用户一个正式入口查看照片资产、人物确认结果、故事和时间线。
  - 做完你能看到什么：用户能真正看到这条能力，而不是只有接口和后台任务。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 6、需求 7
    - `design.md` §2.3.6
    - `design.md` §3.4「建议文件结构」
    - `apps/user-web/src/pages/`
  - 主要改哪里：
    - `apps/user-web/src/pages/PhotosPage.tsx`
    - `apps/user-web/src/components/PhotoFaceBindingPanel.tsx`
    - `apps/user-web/src/components/PhotoStoryComposer.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 这一步先不做什么：先不做重型瀑布流相册，不做完整图库替代体验。
  - 怎么算完成：
    1. 有正式照片页面或入口
    2. 能查看照片列表、详情、人物绑定状态、时间线
    3. 能触发故事生成和手动重跑分析
  - 怎么验证：
    - 前后端联调
    - 手工回归
  - 对应需求：`requirements.md` 需求 5、需求 6、需求 7
  - 对应设计：`design.md` §2.3.5、§2.3.6、§3.4

- [ ] 4.3 整理第一批后端数据模型和 Pydantic schema
  - 状态：TODO
  - 这一步到底做什么：把第一批 `photo` 模块的数据模型、读写 schema、同步契约 schema 先整理成可落代码草案，避免实现时边写边猜。
  - 做完你能看到什么：后端开始动手前，模型和接口字段已经成型，迁移、service、API 能按同一套字段说话。
  - 先依赖什么：2.7
  - 开始前先看：
    - `design.md` §3.2「数据结构」
    - `design.md` §3.3.7.1、§3.3.7.2
    - `apps/api-server/app/modules/plugin/schemas.py`
  - 主要改哪里：
    - `specs/007-照片与相册基础能力/docs/`
    - `apps/api-server/app/modules/photo/models.py`
    - `apps/api-server/app/modules/photo/schemas.py`
  - 这一步先不做什么：先不一次性把全部前端类型也补齐。
  - 怎么算完成：
    1. 第一批 SQLAlchemy model 草案成型
    2. 第一批 Pydantic schema 草案成型
    3. `ImmichConnector` 输入输出字段能和本地 schema 对上
  - 怎么验证：
    - 人工走查字段一致性
    - schema 校验测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 7
  - 对应设计：`design.md` §3.2、§3.3.7.1、§3.3.7.2

- [ ] 4.4 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 已经能指导后续分阶段实现，而不是只写了一堆看起来很完整的空话。
  - 做完你能看到什么：后续接手的人知道先补哪条主链，哪里能复用，哪里明确先不做。
  - 先依赖什么：4.1、4.2、4.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再扩新范围。
  - 怎么算完成：
    1. 照片接入、分析、成员绑定、记忆写回、故事、时间线都有明确落点
    2. 与 `conversation`、`plugin_job`、`memory`、`Immich` 的边界写清楚，并明确文件在外部、语义在本地
    3. 风险和延期项写清楚，没有把第一版膨胀成相册平台重构
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
