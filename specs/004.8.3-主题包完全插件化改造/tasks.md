# 任务清单 - 主题包完全插件化改造（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只回答一件事：怎么把主题包从“展示上像插件”推进到“资源层彻底插件化”，并同时覆盖 `apps/api-server`、`apps/user-app` 的 H5 和 RN。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等待复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不再继续

---

## 阶段 1：先把主题插件模型收口

- [ ] 1.1 把现有 8 套默认主题迁成真实插件目录
  - 状态：TODO
  - 这一步到底做什么：把现有默认主题都改成真实 `theme-pack` 插件目录、manifest 和 token 资源文件。
  - 做完以后你能看到什么：默认主题不再主要活在宿主静态列表里，而是和第三方主题包一样是正式插件。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 2.1、3.2
  - 主要改哪些文件：
    - `apps/api-server/app/plugins/builtin/`
    - `apps/api-server/app/modules/plugin/theme_registry.py`
    - `packages/user-core/src/state/theme.ts`
    - `packages/user-ui/src/theme/`
  - 这一步先不做什么：先不改插件市场安装链路。
  - 怎么算完成：
    1. 8 套默认主题都有真实插件目录和 manifest
    2. 宿主静态主题列表不再承担 canonical source 角色
    3. 登录前启动主题来自内置 `theme-pack` 插件资源，而不是 `themes.ts` 静态主题表
  - 怎么验证：
    - manifest 校验测试
    - 插件目录人工检查
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 2.1、3.2

- [ ] 1.2 扩展主题插件 manifest 与资源索引协议
  - 状态：TODO
  - 这一步到底做什么：补齐 `resource_source`、`resource_version`、`platform_targets`、`entry_resource`、`theme_schema_version` 等资源字段。
  - 做完以后你能看到什么：内置和远端主题插件都能用同一套 schema 描述资源。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 3.1、3.2
  - 主要改哪些文件：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/tests/test_plugin_manifest.py`
  - 这一步先不做什么：先不改前端运行时。
  - 怎么算完成：
    1. `theme-pack` manifest 能完整描述资源来源和版本
    2. 内置与远端主题插件都能通过同一份校验逻辑
  - 怎么验证：
    - schema 单元测试
    - 现有与新增 manifest 样例回归
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 3.1、3.2

- [ ] 1.3 阶段检查：确认宿主不再是主题资源源
  - 状态：TODO
  - 这一步到底做什么：确认默认主题已经完成插件化，宿主只剩运行时和平台适配逻辑。
  - 做完以后你能看到什么：后面迁移 H5/RN 时，不会再被旧静态主题表拖回去。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：当前阶段全部相关文件
  - 这一步先不做什么：不扩展新主题范围。
  - 怎么算完成：
    1. 默认主题插件目录齐全
    2. 宿主不再保留正式 fallback 主题资源
  - 怎么验证：
    - 人工走查
    - 关键测试通过
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 2.1、6.1

---

## 阶段 2：把 H5 和 RN 统一切到主题插件运行时

- [ ] 2.1 重写后端主题注册表与资源接口
  - 状态：TODO
  - 这一步到底做什么：新增主题注册表接口和主题 token 正文接口，替代当前宿主虚拟主题目录逻辑。
  - 做完以后你能看到什么：前端可以先拿主题列表，再按需拿 token 正文，不再靠宿主静态定义兜底。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` 3.3、5.3
  - 主要改哪些文件：
    - `apps/api-server/app/modules/plugin/service.py`
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`
    - 主题相关测试文件
  - 这一步先不做什么：先不改前端页面样式细节。
  - 怎么算完成：
    1. 后端能返回主题注册表快照
    2. 后端能按插件 ID 和主题 ID 返回 token 正文
  - 怎么验证：
    - API 集成测试
    - 权限与启停场景回归
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` 3.3、4.2

- [ ] 2.2 建立前端统一主题插件运行时
  - 状态：TODO
  - 这一步到底做什么：让 H5 和 RN 都通过同一套主题插件运行时，加上“内置 bundle 解析器 + 远端资源解析器”统一选择、加载、缓存和失效处理主题资源。
  - 做完以后你能看到什么：登录页、未登录壳层、业务页都不再直接依赖宿主静态主题定义，首屏也能从内置插件稳定启动。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.2、2.3、6.2
  - 主要改哪些文件：
    - `apps/user-app/src/runtime/`
    - `apps/user-app/src/runtime/h5-shell/theme/`
    - `apps/user-app/src/runtime/rn-shell/`
    - `packages/user-core/src/state/theme.ts`
    - `packages/user-ui/src/theme/`
  - 这一步先不做什么：先不顺手重做整个设计系统。
  - 怎么算完成：
    1. H5 和 RN 都走统一主题插件运行时
    2. 主题插件失效时进入明确待重选状态
    3. 登录前首屏只读内置 `theme-pack` 插件资源，登录后再叠加远端插件
  - 怎么验证：
    - 前端单元测试
    - H5/RN 页面联调回归
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` 2.2、2.3、4.2

- [ ] 2.3 阶段检查：H5 和 RN 主题链路打通
  - 状态：TODO
  - 这一步到底做什么：确认两端都已经不再依赖宿主默认主题源。
  - 做完以后你能看到什么：业务页、登录页和设置页都能按插件主题运行。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：当前阶段全部相关文件
  - 这一步先不做什么：不顺手重做其它插件类型。
  - 怎么算完成：
    1. H5 和 RN 都能切换插件主题
    2. 失效、禁用、卸载状态有统一提示
  - 怎么验证：
    - 页面回归
    - 状态流转检查
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` 2.3、4.2、5.3

---

## 阶段 3：补齐插件安装同步和最终验收

- [ ] 3.1 把主题插件安装、升级、卸载同步接进资源链路
  - 状态：TODO
  - 这一步到底做什么：让插件市场和手动挂载在主题资源层也能形成闭环。
  - 做完以后你能看到什么：远端主题插件装上就能被注册、升级后版本会变化、卸载后前端会感知失效。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` 2.3.2、3.3、5.3
  - 主要改哪些文件：
    - `apps/api-server/app/modules/plugin_marketplace/`
    - `apps/api-server/app/modules/plugin/startup_sync_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：不扩展插件签名或商业化校验。
  - 怎么算完成：
    1. 安装后注册表可见新主题插件
    2. 升级和卸载后前端能感知版本或失效变化
  - 怎么验证：
    - 插件安装链路测试
    - 升级/卸载回归测试
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` 2.3.2、3.3、4.2

- [ ] 3.2 最终检查：主题包彻底插件化
  - 状态：TODO
  - 这一步到底做什么：确认这份改造已经达到“宿主不留主题 fallback，也不留宿主静态主题源”的交付标准。
  - 做完以后你能看到什么：主题资源归属、运行时、安装同步和错误语义都能对上。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪些文件：当前 Spec 全部文件
  - 这一步先不做什么：不新增新的主题包需求。
  - 怎么算完成：
    1. 内置和远端主题插件都遵守同一模型
    2. H5/RN 主题运行时统一
    3. 宿主不再承担正式主题 fallback
  - 怎么验证：
    - 需求逐条对照
    - 测试证据汇总
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
