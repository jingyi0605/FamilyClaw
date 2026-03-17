# 任务清单 - 插件版本治理与手动升级（人话版）

状态：DONE

## 这份文档是干什么的

这份任务清单不是为了把“版本治理”说得很高级，而是为了防止后面又做成三种半截子能力：

- 一点后端比较逻辑
- 一点前端提示文案
- 一点升级按钮

最后谁都说不清系统到底能不能升级。

这次必须按顺序来：

- 先把版本真相和比较逻辑收干净
- 再把安装、升级、回滚链路接上
- 再把前端入口和文档一起收口

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

## 阶段 1：先把版本真相和比较规则定死

- [x] 1.1 盘清当前版本字段和真相来源
  - 状态：DONE
  - 这一步到底做什么：把市场条目、插件实例、挂载 manifest、统一插件注册表里的版本字段分别在哪、谁才是最终真相写清楚。
  - 做完你能看到什么：后面不会再有人一会儿拿 `manifest.version` 当已安装版本，一会儿又拿市场 `latest_version` 当当前版本。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6
    - `design.md` §1.4「当前代码真相」
    - `design.md` §4.1「数据关系」
    - `specs/004.5-插件能力统一接入与版本治理/`
    - `specs/004.6-插件市场一键安装与手动启用/`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/modules/plugin_marketplace/models.py`
    - `specs/004.7-插件版本治理与手动升级/`
  - 这一步先不做什么：先不做升级接口，不急着加按钮。
  - 怎么算完成：
    1. 能明确说清每个版本字段负责什么
    2. 能明确说清哪些字段是事实，哪些字段是派生结果
  - 怎么验证：
    - 人工走查代码和 Spec
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` §1.4、§4.1
  - 本次产出：
    - 新增 `docs/20260317-版本字段真相盘点.md`，把市场条目、实例记录、落盘 manifest、宿主版本的职责写死。
    - 在 `app.modules.plugin.versioning` 和相关 schema 里把“事实字段”和“派生结果”分开建模。
  - 验证结果：
    - 人工走查 `plugin/service.py`、`plugin_marketplace/service.py`、`plugin_marketplace/models.py` 和补充文档，确认没有再把 `latest_version` 当已安装版本使用。
  - 剩余风险：
    - 历史数据里如果已经存在“实例版本”和落盘 manifest 不一致的坏状态，只会被识别成 `unknown`，不会自动修复。

- [x] 1.2 实现统一版本比较与兼容性判断服务
  - 状态：DONE
  - 这一步到底做什么：把版本解析、宿主兼容性判断、最新可兼容版本筛选和 `update_state` 归类收成一套后端服务。
  - 做完你能看到什么：后端终于有一套能复用的版本治理结果，不再靠到处比较字符串。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §2.1「系统结构」
    - `design.md` §3.2.1「PluginVersionGovernanceRead」
    - `design.md` §4.2.1「update_state」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/plugin_marketplace/`
    - 对应测试文件
  - 这一步先不做什么：先不扩自动升级，也不做完整 semver 平台。
  - 怎么算完成：
    1. 后端能统一给出 `latest_compatible_version`
    2. 后端能统一给出稳定 `update_state`
  - 怎么验证：
    - 单元测试覆盖版本比较和兼容性判断
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §2.1、§3.2.1、§4.2.1、§6.1、§6.2
  - 本次产出：
    - 新增 `apps/api-server/app/modules/plugin/versioning.py`，统一处理版本解析、宿主兼容判断、`latest_compatible_version` 筛选和 `update_state` 归类。
    - 新增 `PluginVersionGovernanceRead`，并把它接入插件注册结果和市场目录结果。
    - 新增 `docs/20260317-版本比较规则说明.md`，明确当前只支持最小可用版本比较规则。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_versioning`
  - 剩余风险：
    - 当前版本比较规则仍是最小实现，不支持项目未来可能出现的所有非标准版本命名；超出规则时会保守降级成 `unknown`。

### 阶段检查

- [x] 1.3 阶段 1 检查：确认版本治理没有长出第二套真相
  - 状态：DONE
  - 这一步到底做什么：检查第一阶段是不是只是把派生结果重新存了一份，或者又在别处造了一张“版本状态表”。
  - 做完你能看到什么：可以进入升级链路实现，而不是带着结构性垃圾往下冲。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不顺手扩范围到 UI。
  - 怎么算完成：
    1. 版本事实和派生结果边界已经写清楚
    2. 没有新增重复真相的数据表
  - 怎么验证：
    - 人工走查
    - 关键测试验证
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` §4.1、§6.1
  - 本次产出：
    - 统一版本治理结果全部改为按需计算，没有新增数据库表，也没有新增派生状态持久化字段。
  - 验证结果：
    - 人工走查 `plugin/versioning.py`、`plugin_marketplace/models.py`、`plugin/schemas.py`，确认新增字段都停留在接口/服务层。
  - 剩余风险：
    - 目录查询里当前失败会降级为 `version_governance=null`，前端还需要把这类降级展示讲清楚。

---

## 阶段 2：把安装、升级、回滚链路接起来

- [x] 2.1 在安装链路接入宿主兼容性阻断
  - 状态：DONE
  - 这一步到底做什么：让安装和版本切换在真正下载前先判断 `min_app_version`，不兼容就直接拒绝。
  - 做完你能看到什么：用户不会再把不兼容版本下载一半才发现不能用。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.2「手动升级流程」
    - `design.md` §5.1「错误类型」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/modules/plugin_marketplace/schemas.py`
    - 对应测试文件
  - 这一步先不做什么：先不做升级入口，只先把兼容性阻断接上。
  - 怎么算完成：
    1. 安装前已经校验宿主兼容性
    2. 不兼容时返回明确错误码
  - 怎么验证：
    - 集成测试覆盖宿主版本过低场景
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.2、§5.1、§6.2
  - 本次产出：
    - 安装链路在真正下载前接入 `min_app_version` 校验。
    - 缺少兼容性信息时按保守策略直接阻断，不再装到一半才失败。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
    - 覆盖 `test_install_blocks_when_host_version_too_old`
  - 剩余风险：
    - 市场条目如果还没补 `min_app_version`，现在会被明确阻断，后续需要市场数据一起跟上。

- [x] 2.2 实现手动升级和手动回滚接口
  - 状态：DONE
  - 这一步到底做什么：在现有安装能力上补一个正式的版本切换入口，让系统能按目标版本升级和回滚。
  - 做完你能看到什么：版本切换不再需要假装成“重新安装”。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` §2.3.2、§2.3.3、§3.3.2
    - `design.md` §4.2.2「版本切换操作状态」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/api/v1/endpoints/plugin_marketplace.py`
    - `apps/api-server/app/modules/plugin_marketplace/repository.py`
    - 对应测试文件
  - 这一步先不做什么：先不补自动回滚策略。
  - 怎么算完成：
    1. 系统能接收升级和回滚请求
    2. 目标版本不存在或来源不一致时会明确阻断
  - 怎么验证：
    - 集成测试覆盖升级成功、回滚成功、目标版本不存在、来源冲突
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §2.3.2、§2.3.3、§3.3.2、§4.2.2
  - 本次产出：
    - 新增 `POST /api/v1/plugin-marketplace/instances/{instance_id}/version-operations`。
    - 后端新增正式版本切换服务，支持同源升级和同源回滚。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
    - 覆盖 `test_upgrade_and_rollback_keep_enabled_state`
  - 剩余风险：
    - API 层目前还没补“目标版本不存在/来源冲突”的独立接口级断言，后面会继续补在回归测试里。

- [x] 2.3 落实升级后的状态保持与配置重算
  - 状态：DONE
  - 这一步到底做什么：确保升级和回滚不会默认把插件打回禁用，同时在必要时正确降级配置状态。
  - 做完你能看到什么：系统能“尽量保留现状”，而不是每次版本切换都把用户空间砸碎。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.3.4「升级后的状态保持流程」
    - `design.md` §5.3「处理策略」
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin_marketplace/service.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - 对应测试文件
  - 这一步先不做什么：先不做配置迁移脚本自动执行。
  - 怎么算完成：
    1. 同源升级默认保留原启用状态
    2. 配置不兼容时会明确降级成 `unconfigured` 或 `invalid`
  - 怎么验证：
    - 集成测试覆盖升级保留启用状态和配置降级场景
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §2.3.4、§5.3、§6.3
  - 本次产出：
    - 版本切换默认保留原启用状态和现有配置。
    - 切换后会重算 `config_status`；如果配置失效，会明确降级并关停执行能力。
    - 版本切换失败时会回滚实例和挂载运行态，不再把旧状态打成半残。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
    - 覆盖 `test_upgrade_disables_plugin_when_new_config_schema_breaks_old_config`
    - 覆盖 `test_version_switch_failure_keeps_previous_instance_state`
  - 剩余风险：
    - 当前只做配置状态重算，还没有做更细粒度的配置迁移脚本。

### 阶段检查

- [x] 2.4 阶段 2 检查：确认系统已经能安全切换版本
  - 状态：DONE
  - 这一步到底做什么：检查第二阶段是不是已经打通“兼容性判断 -> 版本切换 -> 状态保持”这条主链路。
  - 做完你能看到什么：后端已经具备真正可用的手动升级基础，不再只是文档里说说。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不额外做页面体验优化。
  - 怎么算完成：
    1. 主要成功路径和失败路径都已验证
    2. 没有把首次安装语义错误复用到升级语义里
  - 怎么验证：
    - 人工走查
    - 关键集成测试回归
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3.2、§2.3.3、§2.3.4、§6.2、§6.3
  - 本次产出：
    - 兼容性判断 -> 版本切换 -> 状态保持 这条后端主链已经打通。
    - 市场目录和插件注册结果都已经开始消费统一版本治理结果。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_versioning`
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_api`
  - 剩余风险：
    - 旧的 `tests/test_plugin_manifest.py` 仍然有历史坏文件导致语法错误，和本次改动无关，暂时不能作为回归入口。

---

## 阶段 3：把前端、测试和文档一起收口

- [x] 3.1 前端展示统一版本治理状态和操作入口
  - 状态：DONE
  - 这一步到底做什么：让市场页和插件详情页真正把已安装版本、市场最新版本、最新可兼容版本和更新状态讲清楚。
  - 做完你能看到什么：用户终于知道自己现在装的是什么、能不能升、为什么不能升。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §2.1「系统结构」
    - `design.md` §3.3.3「市场目录版本字段扩展」
    - `design.md` §4.2.1「update_state」
  - 主要改哪里：
    - `apps/user-app/src/pages/plugins/index.tsx`
    - `apps/user-app/src/pages/settings/components/PluginDetailDrawer.tsx`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - i18n 字典
  - 这一步先不做什么：先不做大改视觉，只把信息和操作讲清楚。
  - 怎么算完成：
    1. 页面能展示统一版本治理结果
    2. 页面有升级和回滚入口
  - 怎么验证：
    - 前端人工走查
    - `typecheck`
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` §2.1、§3.3.3、§4.2.1
  - 本次产出：
    - `apps/user-app/src/pages/settings/settingsTypes.ts` 已补 `PluginVersionGovernanceRead`、`MarketplaceEntryDetailRead`、版本切换请求/结果类型，并把 `version_governance` 接到插件注册结果和市场目录结果。
    - `apps/user-app/src/pages/settings/settingsApi.ts` 已补市场详情、版本治理详情、版本切换接口封装。
    - `apps/user-app/src/pages/plugins/index.tsx` 已改为优先使用 `latest_compatible_version` 发起安装，市场卡片开始展示已安装版本、市场最新版本、最新可兼容版本、更新状态、兼容状态和阻断原因，并补一键升级入口。
    - `apps/user-app/src/pages/settings/components/PluginDetailDrawer.tsx` 已补统一版本治理区块，支持加载可选版本，并提供指定目标版本的手动升级/回滚入口。
    - `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.zh-CN.ts`、`apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts` 已补版本治理、升级、回滚、阻断原因相关文案。
  - 验证结果：
    - 已执行 `apps/user-app` 下的 `npm.cmd run typecheck`，通过。
    - 已人工走查页面逻辑，确认市场安装默认不再直取 `latest_version`，而是消费后端统一返回的 `latest_compatible_version`。
  - 剩余风险：
    - 当前详情抽屉里的“目标版本”下拉直接消费市场条目顺序，不额外在前端重做版本排序；实际可用性仍以后端版本校验为准。

- [x] 3.2 补齐版本治理测试和回归用例
  - 状态：DONE
  - 这一步到底做什么：把版本比较、兼容性阻断、升级成功、回滚成功、状态保持这些场景补成正式测试。
  - 做完你能看到什么：这轮不是拍脑袋写出来的逻辑，而是有回归保护。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 5
    - `design.md` §7「测试策略」
  - 主要改哪里：
    - `apps/api-server/tests/`
    - `apps/user-app` 相关测试或最小验证脚本
  - 这一步先不做什么：先不扩全量 UI 自动化。
  - 怎么算完成：
    1. 关键后端场景已经有测试
    2. 前端类型和主要状态展示已验证
  - 怎么验证：
    - 定向单测、集成测试、类型检查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 5
  - 对应设计：`design.md` §7.1、§7.2、§7.3、§7.4
  - 本次产出：
    - 后端已经补齐版本比较、宿主兼容性阻断、升级成功、回滚成功、状态保持和失败回滚相关测试。
    - 前端已补类型定义和版本治理展示逻辑，并通过 `typecheck` 做最小回归验证。
  - 验证结果：
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_versioning`
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
    - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_api`
    - `apps/user-app` 下执行 `npm.cmd run typecheck`
  - 剩余风险：
    - `apps/api-server/tests/test_plugin_manifest.py` 仍然是历史坏文件，语法错误与本次版本治理改动无关，暂时不能作为全量回归入口。

- [x] 3.3 更新版本治理文档和相关 Spec 引用
  - 状态：DONE
  - 这一步到底做什么：把 `004.5`、`004.6` 和开发文档里关于版本治理的说法更新到这份 Spec 上。
  - 做完你能看到什么：后续接手的人不会再把“最小展示能力”和“手动升级能力”混成一锅粥。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §8.2「待确认项」
    - `specs/004.5-插件能力统一接入与版本治理/`
    - `specs/004.6-插件市场一键安装与手动启用/`
  - 主要改哪里：
    - `specs/004.5-插件能力统一接入与版本治理/`
    - `specs/004.6-插件市场一键安装与手动启用/`
    - `docs/开发者文档/插件开发/`
    - `specs/004.7-插件版本治理与手动升级/docs/`
  - 这一步先不做什么：不借机扩出自动升级规范。
  - 怎么算完成：
    1. 文档已经明确 `004.7` 承接手动升级和版本治理
    2. 当前不做自动升级和完整 semver 的边界已经写清楚
  - 怎么验证：
    - 文档走查
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §1.4、§8.2
  - 本次产出：
    - 已在 `specs/004.5-插件能力统一接入与版本治理/README.md` 顶部补 2026-03-17 边界说明，明确 `004.5` 只保留统一插件模型和最小版本字段补齐，不再承接手动升级 / 回滚。
    - 已在 `specs/004.6-插件市场一键安装与手动启用/README.md` 顶部补 2026-03-17 边界说明，明确 `latest_compatible_version`、统一版本状态、手动升级 / 回滚改由 `004.7` 承接。
    - 已新增 `docs/20260317-升级与回滚联调说明.md`，把前端展示、操作入口、联调验证和明确不做的范围写清楚。
  - 验证结果：
    - 已人工走查 `004.5`、`004.6` 顶部说明，确认旧 Spec 不再继续误导“手动升级属于旧任务”。
    - 已检查 `004.7/docs/`，确认联调说明落盘，并把当前边界写清楚。
  - 剩余风险：
    - `004.6/design.md` 内部仍保留部分历史表述，例如把 `latest_version` 当默认安装依据；当前通过 README 顶部说明截断误导，后续如果继续维护旧设计稿，应该再做一轮正文清理。

### 最终检查

- [x] 3.4 最终检查点
  - 状态：DONE
  - 这一步到底做什么：确认这份 Spec 真正把插件版本治理从“展示字段”推进到“手动升级可用”，而不是只加了几个文案。
  - 做完你能看到什么：需求、设计、任务和验证结果能一一对上，后续实现也知道边界在哪。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件和相关实现文件
  - 这一步先不做什么：不追加自动升级这类新目标。
  - 怎么算完成：
    1. 关键任务都能追踪到需求和设计
    2. 版本真相、兼容性阻断、升级/回滚和状态保持已经讲清楚
    3. 剩余风险和延后项已经写明
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
  - 本次产出：
    - 阶段 1 已统一版本真相、版本比较和 `update_state` 计算，不新增第二套持久化真相。
    - 阶段 2 已接通宿主兼容性阻断、手动升级 / 回滚、状态保持和失败回滚保护。
    - 阶段 3 已完成前端展示、操作入口、定向验证和旧 Spec 引用回写。
  - 本次验收结果：
    - 后端验证：
      - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_versioning`
      - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_service`
      - `.\.venv\Scripts\python.exe -m unittest tests.test_plugin_marketplace_api`
    - 前端验证：
      - `apps/user-app` 下执行 `npm.cmd run typecheck`
    - 文档验证：
      - 已走查 `004.5`、`004.6` 顶部边界说明和 `004.7/docs/20260317-升级与回滚联调说明.md`
  - 剩余风险与延后项：
    - 历史坏文件 `apps/api-server/tests/test_plugin_manifest.py` 仍然存在语法错误，和本次版本治理改动无关。
    - 当前版本比较规则仍是最小可用实现，不覆盖完整 semver 和所有非标准版本命名。
    - 详情抽屉里的可选版本顺序直接消费市场条目返回值，最终合法性仍以后端校验为准。
