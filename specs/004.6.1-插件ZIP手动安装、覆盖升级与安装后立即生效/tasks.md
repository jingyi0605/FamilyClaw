# 任务清单 - 插件 ZIP 手动安装、覆盖升级与安装后立即生效（人话版）

状态：DONE

## 这份文档是干什么的

这份任务清单不是为了把“上传 ZIP”拆成几十个花活。

它只回答几件事：

- 先把哪条后端链路收干净
- 哪一步在定“立即生效”的边界
- 哪一步在补前端上传体验
- 做完以后怎么证明市场插件和 ZIP 插件都不需要重启服务

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- `BLOCKED` 必须写清楚卡在哪里
- `CANCELLED` 必须写清楚为什么不做
- 每做完一个任务，必须立刻更新这里

---

## 阶段 1：先把运行时安装和“立即生效”边界定死

- [x] 1.1 盘清现有手工挂载、市场安装和运行时执行边界
  - 状态：DONE
  - 这一步到底做什么：把当前 ZIP 手工安装缺什么、市场插件现在如何生效、哪些地方还带着“可能要重启”的模糊口径盘清楚。
  - 做完你能看到什么：后面不会一边写 ZIP 上传，一边继续把市场插件语义写散。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5、需求 6、需求 7
    - `design.md` §2.1「系统结构」
    - `design.md` §2.3.3「安装后立即生效流程」
    - `specs/004.6-插件市场一键安装与手动启用/`
    - `specs/004.7-插件版本治理与手动升级/`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/executors.py`
    - `apps/api-server/app/modules/plugin/job_worker.py`
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
  - 这一步先不做什么：先不改前端上传 UI。
  - 怎么算完成：
    1. 当前“无需重启”的真实边界已经写清楚
    2. 已确认运行时安装插件应该统一走哪种执行后端
  - 怎么验证：
    - 已有后端实现通过 `install_plugin_package`、`set_marketplace_instance_enabled`、`operate_marketplace_instance_version` 和任务 worker 链路体现运行时边界
    - 人工走查代码和 Spec
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 6、需求 7
  - 对应设计：`design.md` §2.1、§2.3.3、§2.3.4、§2.3.5

- [x] 1.2 定义 ZIP 安装结果模型和错误语义
  - 状态：DONE
  - 这一步到底做什么：把上传 ZIP 后返回什么、覆盖升级怎么确认、失败怎么报错一次写清楚。
  - 做完你能看到什么：前后端不会各自发明一套安装成功和失败状态。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3、需求 8
    - `design.md` §3.2「数据结构」
    - `design.md` §5「错误处理」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
  - 这一步先不做什么：先不接真实解压安装。
  - 怎么算完成：
    1. ZIP 上传安装请求和响应 schema 已固定
    2. 覆盖升级、坏包、切换失败都有稳定错误码
  - 怎么验证：
    - 后端已落 `PluginPackageInstallRead`
    - `POST /api/v1/ai-config/{household_id}/plugin-packages` 已固定 `multipart/form-data + overwrite`
    - 人工走查接口契约
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 8
  - 对应设计：`design.md` §3.2、§3.3.1、§5

### 阶段检查

- [x] 1.3 阶段检查：确认“立即生效”没有被写成假热重载
  - 状态：DONE
  - 这一步到底做什么：专门检查文案、接口和设计有没有偷偷把“下一次执行生效”说成模块热替换。
  - 做完你能看到什么：后面不会被一句假话拖死实现。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩新需求。
  - 怎么算完成：
    1. 文案里没有“已完成 Python 热重载”这类假话
    2. 生效边界和任务边界已经写清楚
  - 怎么验证：
    - 已在本 spec 和正式文档回写“无需重启后端服务即可被列表和后续执行识别，但不是 Python 模块热替换”
    - 人工走查
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 6、需求 8
  - 对应设计：`design.md` §2.3.3、§2.3.4、§5.3、§6

---

## 阶段 2：打通 ZIP 上传安装和覆盖升级后端链路

- [x] 2.1 实现 ZIP 上传、临时解压和安全校验
  - 状态：DONE
  - 这一步到底做什么：让后端能接住 ZIP 文件，安全解压并校验 `manifest.json`、入口和路径。
  - 做完你能看到什么：坏 ZIP 包在进入挂载前就被挡住。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §2.3.1「ZIP 首次安装流程」
    - `design.md` §5.1「错误类型」
  - 主要改哪里：
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - 对应测试文件
  - 这一步先不做什么：先不切换正式挂载。
  - 怎么算完成：
    1. ZIP 文件上传可用
    2. 非法 ZIP、缺 manifest、路径穿越都被阻断
  - 怎么验证：
    - 后端已有 `POST /api/v1/ai-config/{household_id}/plugin-packages`
    - 服务侧已做 ZIP 后缀校验、空包校验、解压、manifest 解析和冲突判断
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §2.3.1、§3.3.1、§5.1

- [x] 2.2 实现托管到版本目录和首次安装挂载
  - 状态：DONE
  - 这一步到底做什么：把校验通过的 ZIP 包复制到托管版本目录，并创建首次挂载。
  - 做完你能看到什么：用户第一次上传 ZIP 后，插件能进入插件列表，但仍默认未启用。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4、需求 5
    - `design.md` §2.3.1、§3.2.3、§4.1
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/models.py`
    - 对应测试文件
  - 这一步先不做什么：先不做覆盖升级。
  - 怎么算完成：
    1. 托管目录变成按版本落盘
    2. 首次安装后能从现有插件列表接口看到新挂载
  - 怎么验证：
    - 手动 ZIP 安装目录已落到 `/data/plugins/third_party/manual/<household_id>/<plugin_id>/<version>--<timestamp>--<id>/`
    - 首次安装会创建 `PluginMount`，并固定 `execution_backend=subprocess_runner`
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` §2.3.1、§3.2.3、§4.1、§4.3

- [x] 2.3 实现覆盖升级挂载切换和失败回滚
  - 状态：DONE
  - 这一步到底做什么：同插件 ID 上传新 ZIP 时，把新版本落到新目录，再原子切换挂载，失败就回滚。
  - 做完你能看到什么：用户不需要先删旧插件再装新版本。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 8
    - `design.md` §2.3.2「ZIP 覆盖升级流程」
    - `design.md` §6.1「新挂载切换原子化」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/repository.py`
    - 对应测试文件
  - 这一步先不做什么：先不做手工 ZIP 历史版本回滚。
  - 怎么算完成：
    1. 不确认覆盖时会被明确阻断
    2. 确认覆盖后能切到新版本
    3. 切换失败时旧挂载仍可用
  - 怎么验证：
    - 现有实现要求 `overwrite=true`
    - 覆盖升级会切换 `PluginMount.plugin_root / manifest_path / working_dir`
    - 异常时接口事务回滚，目标目录清理，旧挂载继续保留
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 8
  - 对应设计：`design.md` §2.3.2、§5.3、§6.1

### 阶段检查

- [x] 2.4 阶段检查：确认 ZIP 安装链路已经能不靠重启落地
  - 状态：DONE
  - 这一步到底做什么：检查从上传到挂载切换这条链是不是已经闭环，不再依赖服务重启补状态。
  - 做完你能看到什么：ZIP 安装已经是正式能力，不是半成品。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不顺手改市场前端体验。
  - 怎么算完成：
    1. 上传 ZIP 后刷新列表可见
    2. 覆盖升级后刷新列表直接看到新版本
    3. 不存在“安装成功但必须重启才认到”的情况
  - 怎么验证：
    - 列表和执行链路都从当前 `PluginMount` / 家庭插件快照读取
    - 手动 ZIP 安装和覆盖升级不再依赖服务重启补状态
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4、需求 8
  - 对应设计：`design.md` §2.3.1、§2.3.2、§2.3.3、§6.2

---

## 阶段 3：统一运行时生效边界和前端体验

- [x] 3.1 收口运行时安装插件的执行后端与任务边界
  - 状态：DONE
  - 这一步到底做什么：把运行时安装插件的执行后端、运行中任务边界、待执行任务边界统一收口。
  - 做完你能看到什么：ZIP 插件和市场插件对“无需重启”说的是同一件事。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 5、需求 6、需求 7
    - `design.md` §2.3.4「任务与执行边界流程」
    - `design.md` §2.3.5「市场安装一致性流程」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/executors.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin/job_worker.py`
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
  - 这一步先不做什么：不碰内置插件运行模型。
  - 怎么算完成：
    1. 运行时安装插件统一按既定隔离执行边界运行
    2. 已运行任务和待执行任务的行为可预测
    3. 市场安装、启用、升级都明确不需要重启后端
  - 怎么验证：
    - 手动 ZIP 安装固定 `subprocess_runner`
    - 插件任务 worker 在真正执行时重新构造请求并走当前插件快照/挂载
    - 市场安装默认 `enabled=false`，启用要求 `install_status=installed && config_status=configured`
    - 市场升级和回滚直接切换当前挂载，不要求重启后端
  - 对应需求：`requirements.md` 需求 5、需求 6、需求 7
  - 对应设计：`design.md` §2.3.4、§2.3.5、§4.3、§6.2、§6.3

- [x] 3.2 完成插件管理页 ZIP 上传、覆盖确认和结果展示
  - 状态：DONE
  - 这一步到底做什么：在 `user-app` 插件管理页补上传入口、覆盖确认、安装结果提示和即时刷新。
  - 做完你能看到什么：管理员在页面里就能把 ZIP 包装进去，不需要碰命令行。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4、需求 8
    - `design.md` §2.3.1、§2.3.2、§3.3.1
    - `docs/开发设计规范/前端页面设计语言规范.md`
  - 主要改哪里：
    - `apps/user-app/src/pages/plugins/index.tsx`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - i18n 字典
  - 这一步先不做什么：不额外搞复杂拖拽上传和批量安装。
  - 怎么算完成：
    1. 页面可选择 ZIP 上传
    2. 同插件上传时会要求确认覆盖
    3. 成功后自动刷新列表和详情
  - 怎么验证：
    - `plugins` 页面已补 ZIP 上传入口、覆盖确认弹窗、成功提示和自动刷新
    - `cmd /c npm run test:plugins-page` 已通过
    - `cmd /c npm run typecheck` 已通过
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4、需求 8
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.3.1、§5.3

- [x] 3.3 更新文档和页面文案，明确“无需重启”但“不做热替换”
  - 状态：DONE
  - 这一步到底做什么：把 Spec、正式文档和页面提示统一成同一套口径。
  - 做完你能看到什么：用户和开发者看到的都是同一句真话，不再互相打架。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 7、需求 8
    - `design.md` §5.3、§8.1
    - `specs/004.6-插件市场一键安装与手动启用/README.md`
    - `specs/004.7-插件版本治理与手动升级/README.md`
  - 主要改哪里：
    - 当前 Spec 全部文档
    - `docs/Documentation/` 相关正式文档
    - 前端成功提示和帮助文案
  - 这一步先不做什么：不把这轮扩成完整插件开发者手册重写。
  - 怎么算完成：
    1. 文档明确“不需要重启后端”
    2. 文档明确“不做 Python 模块热替换”
    3. 页面提示不再出现含糊说法
  - 怎么验证：
    - 当前已完成 spec、`docs/Documentation/` 正式文档和页面文案回写
  - 对应需求：`requirements.md` 需求 4、需求 7、需求 8
  - 对应设计：`design.md` §5.3、§8.1、§8.2

### 最终检查

- [x] 3.4 最终检查点
  - 状态：DONE
  - 这一步到底做什么：确认这份 Spec 真正打通了 ZIP 安装、覆盖升级和无需重启生效，而不是只加了一个上传按钮。
  - 做完你能看到什么：需求、设计、任务、文档和验证结果能一一对上。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件和对应实现文件
  - 这一步先不做什么：不再追加新需求。
  - 怎么算完成：
    1. ZIP 安装和覆盖升级已可追踪落地
    2. 市场插件和 ZIP 插件的“无需重启”语义已统一
    3. 风险和明确不做的边界已写清楚
  - 怎么验证：
    - 已核对实现、正式文档、前端文案与 spec
    - 后端已通过 `python -m unittest tests.test_plugin_mounts tests.test_plugin_startup_sync -q`
    - 前端已通过 `cmd /c npm run test:plugins-page`
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
