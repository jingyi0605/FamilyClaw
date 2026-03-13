# 任务清单 - 插件开发规范与注册表（人话版）

状态：Draft

## 这份任务清单怎么用

这份清单不是拿来讨论“生态战略”的，是拿来把插件开发规范和注册表先落成一个可执行版本。

第一版目标只有一个：

- 让第三方开发者能按统一规则开发插件，让市场能按统一规则识别插件

不要一开始就做远程安装和开放执行，不然边界会先烂掉。

## 阶段 1：先把开发规范写稳

- [x] 1.1 写插件开发总指南
  - 状态：已完成（2026-03-13）
  - 这一步到底做什么：把第三方开发者最先会问的问题写成一份总指南，包括插件类型、边界、最小开发流程。
  - 做完你能看到什么：新开发者打开文档就知道第一步看什么、先做什么、哪些先别做。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.1、§2.3.1
    - `specs/004.2-插件系统与外部能力接入/README.md`
  - 主要改哪里：
    - `specs/004.3-插件开发规范与注册表/README.md`
    - `docs/开发者文档/插件开发/`
  - 这一步先不做什么：先不写市场展示，不碰前端界面。
  - 怎么算完成：
    1. 文档说明支持的插件类型和第一版边界
    2. 文档说明开发者最小开发流程
  - 怎么验证：
    - 人工走查文档
    - 让没看过代码的人检查是否能看懂
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.1、§2.3.1

- [x] 1.2 写 manifest 和目录结构规范
  - 状态：已完成（2026-03-13）
  - 这一步到底做什么：把插件目录怎么摆、`manifest.json` 每个字段是什么意思写清楚。
  - 做完你能看到什么：第三方可以按一套稳定格式创建插件，不会乱填字段。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §3.2.1
    - `specs/004.2-插件系统与外部能力接入/docs/20260312-插件-manifest示例.md`
  - 主要改哪里：
    - `specs/004.3-插件开发规范与注册表/design.md`
    - `docs/开发者文档/插件开发/`
  - 这一步先不做什么：先不扩新插件类型，不做向后不兼容改造。
  - 怎么算完成：
    1. `manifest` 字段有清楚说明和约束
    2. 插件目录结构有最小模板
  - 怎么验证：
    - 用现有样板插件人工对照规范
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §3.2.1

### 阶段检查

- [x] 1.3 开发规范检查点
  - 状态：已完成（2026-03-13，已补强插件对接说明）
  - 这一步到底做什么：确认第三方开发者已经能靠规范把插件做出来，而不是还得翻项目源码猜。
  - 做完你能看到什么：后面可以开始写注册表规则和提交流程。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文档
  - 这一步先不做什么：不加注册表市场机制细节。
  - 怎么算完成：
    1. 开发规范已能覆盖最小开发路径
    2. 规则和现有样板插件对得上
  - 怎么验证：
    - 人工走查
    - 样板插件对照检查
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §2.3.1、§3.2.1

## 阶段 2：把注册表和提交流程定下来

- [x] 2.1 定义注册表 schema
  - 状态：已完成（2026-03-13）
  - 这一步到底做什么：定义插件市场识别插件时要读什么字段、怎么区分来源、什么情况下拒绝条目。
  - 做完你能看到什么：官方和第三方注册表能按同一个格式组织数据。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` §3.2.2、§4.1
  - 主要改哪里：
    - `specs/004.3-插件开发规范与注册表/design.md`
    - `docs/开发者文档/插件开发/`
  - 这一步先不做什么：先不做在线商店页面，不做下载协议。
  - 怎么算完成：
    1. 注册表条目字段清楚可校验
    2. 来源类型和风险信息有统一表达
  - 怎么验证：
    - 人工检查 schema
    - 用样例注册项走查
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §3.2.2、§4.1

- [x] 2.2 写 GitHub PR 提交流程和审核清单
  - 状态：已完成（2026-03-13）
  - 这一步到底做什么：把第三方怎么提注册、官方怎么审核写成一份清楚流程。
  - 做完你能看到什么：提交方知道该交什么，审核方知道该看什么。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §2.3.2、§3.3.2、§5.1
  - 主要改哪里：
    - `docs/开发者文档/插件开发/`
    - `specs/004.3-插件开发规范与注册表/README.md`
  - 这一步先不做什么：先不做自动审核机器人，不做签名审批流。
  - 怎么算完成：
    1. PR 提交内容有固定要求
    2. 审核清单能覆盖字段、仓库、文档、风险说明
  - 怎么验证：
    - 人工演练一次第三方提交流程
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §2.3.2、§3.3.2、§5.1

### 阶段检查

- [x] 2.3 注册表规则检查点
  - 状态：已完成（2026-03-13）
  - 这一步到底做什么：确认市场来源和插件提交入口已经有稳定规则，不是靠口头约定。
  - 做完你能看到什么：后面前端插件市场可以直接按这套规则开发。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文档
  - 这一步先不做什么：不扩市场 UI，不做安装机制。
  - 怎么算完成：
    1. 注册表 schema 和 PR 流程能对上
    2. 官方和第三方注册表机制说得清楚
  - 怎么验证：
    - 人工走查
    - 用虚拟插件条目做一次核对
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` §3.2.2、§3.3.2、§4.1

## 阶段 3：补样例和验收说明

- [ ] 3.1 补开发样例和注册表示例
  - 状态：进行中（2026-03-13，已补开发环境、本地调试、测试与项目内运行验证文档；已补同容器子进程 runner 最小设计）
  - 这一步到底做什么：补一套样例，让别人不用靠猜就知道规范长什么样。
  - 做完你能看到什么：至少有 manifest 样例、插件目录样例、注册项样例、PR 示例。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/开发者文档/插件开发/`
  - 主要改哪里：
    - `docs/开发者文档/插件开发/`
  - 这一步先不做什么：不加远程安装脚本，不加执行沙箱说明。
  - 怎么算完成：
    1. 样例能覆盖开发者和维护者两个视角
    2. 样例和规范正文不冲突
  - 怎么验证：
    - 人工走查
    - 用样例反推检查规范是否缺信息
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §3.2、§3.3、§7.2

#### 3.1.A 后端最小重构设计清单：`execute_plugin()` 拆成双执行后端

- 状态：已补设计清单（2026-03-13）
- 这一步到底做什么：在不破坏 `004.2` 已完成底座的前提下，把当前单一同进程执行入口拆成“内置插件同进程执行器”和“第三方插件 runner 执行器”两个后端接口，为后续代码改造收口实现范围。
- 做完你能看到什么：后续新开代码实现会话时，可以直接按模块和顺序落地，不需要再临时猜该拆哪里。
- 先依赖什么：`design.md` 里的 runner 最小设计已经写清楚。
- 开始前先看：
  - `specs/004.3-插件开发规范与注册表/design.md`
  - `apps/api-server/app/modules/plugin/service.py`
  - `apps/api-server/app/modules/plugin/agent_bridge.py`
  - `apps/api-server/app/modules/plugin/schemas.py`
  - `apps/api-server/tests/test_plugin_manifest.py`
  - `apps/api-server/tests/test_plugin_runs.py`
  - `apps/api-server/tests/test_agent_plugin_bridge.py`
  - `apps/api-server/tests/test_action_plugin_permissions.py`
- 主要改哪里：
  - `apps/api-server/app/modules/plugin/service.py`
  - `apps/api-server/app/modules/plugin/agent_bridge.py`
  - `apps/api-server/app/modules/plugin/schemas.py`
  - `apps/api-server/app/modules/plugin/` 下新增 runner 相关模块
  - `apps/api-server/tests/` 相关插件测试
- 这一步先不做什么：
  - 不做自动下载插件源码
  - 不做自动创建 venv
  - 不做自动安装依赖
  - 不做沙箱执行
  - 不做多容器编排
  - 不把内置插件整体迁移到 runner

##### 清单 1：先抽执行后端接口，不先改业务链路

1. 在 `app/modules/plugin/` 下抽一个统一执行后端接口，比如 `PluginExecutor`。
2. 接口最少定义一个执行方法，输入继续复用现有插件执行请求，输出继续复用现有执行结果结构。
3. 当前 `execute_plugin()` 不直接承担 import 和执行细节，而是变成“分发入口”。
4. 原始记录保存、记忆写入、权限校验、审计逻辑先不要挪，避免一上来改散。

##### 清单 2：保留内置插件同进程执行器

1. 新增 `InProcessPluginExecutor`，把现在 `service.py` 里直接 `import_module()` + 调函数的逻辑搬进去。
2. 内置插件继续走当前 `apps/api-server/app/plugins/builtin/` 目录，不改变现有加载方式。
3. 现有测试先默认继续覆盖这条路径，确保 `004.2` 已有能力不回退。

##### 清单 3：新增第三方 runner 执行器

1. 新增 `SubprocessRunnerPluginExecutor`。
2. 第一版只负责：
   - 组装 runner 调用参数
   - 指定插件 venv Python
   - 通过 `stdin/stdout` 传 JSON
   - 解析 stdout JSON 结果
   - 把异常收口成统一错误码
3. runner 执行器不做权限判断，不做数据库写入，不做审计写入。
4. runner 执行失败时，返回统一失败结果，不把 stderr 直接冒充业务返回。

##### 清单 4：补最小执行后端判定规则

1. 系统里必须能判断一个插件该走哪个执行后端。
2. 第一版最简单方案：
   - `builtin` 来源默认走 `in_process`
   - `official` / `third_party` 第三方目录插件默认走 `subprocess_runner`
3. 这个判定可以先放在主服务配置或内部映射里，不要求现在就改完整 manifest schema。
4. 不要为了这一步把现有 manifest 规范全部推倒重来。

##### 清单 5：把 `execute_plugin()` 收成统一分发入口

1. `execute_plugin()` 先做后端判定。
2. 再把执行请求交给对应 executor。
3. 对调用方保持原有返回结构尽量不变，避免上层链路大面积跟着改。
4. 如果返回结构必须加字段，优先追加 `execution_backend`，不要破坏原字段语义。

##### 清单 6：让 `agent_bridge.py` 改成只关心业务，不关心执行方式

1. Agent 桥接仍然只关心：
   - 插件类型是否允许
   - 权限是否允许
   - 是否需要高风险确认
2. 真正执行插件时，统一走新的 `execute_plugin()` 分发入口。
3. 不要把 runner 细节写进 Agent 桥代码里，不然后面又会耦合回去。

##### 清单 7：新增 runner 模块，但先控制到最小

建议最少新增这些文件：

1. `apps/api-server/app/modules/plugin/executors.py`
   - 放执行后端接口和两个 executor 实现
2. `apps/api-server/app/modules/plugin/runner_protocol.py`
   - 放 runner 输入输出 JSON 结构
3. `apps/api-server/app/modules/plugin/runner_errors.py`
   - 放 runner 错误码映射

如果实现时觉得更顺，也可以拆成子目录，但第一版别拆太散。

##### 清单 8：先补最小错误码，不搞大而全

runner 路径至少先收口这些错误：

1. `plugin_runner_not_configured`
2. `plugin_runner_start_failed`
3. `plugin_runner_timeout`
4. `plugin_runner_invalid_output`
5. `plugin_runner_dependency_missing`
6. `plugin_execution_failed`

规则：

- runner 特有错误先保留明确 code
- 对外业务失败仍然统一落到现有插件失败结果结构

##### 清单 9：先补配置项，不做自动化安装

第一版最少要有这些配置：

1. 第三方插件根目录
2. runner Python 路径或 venv 解析规则
3. runner 超时时间
4. stdout/stderr 大小限制
5. runner 工作目录

这里明确不做：

- 自动执行 `pip install`
- 自动探测系统依赖
- 自动修复运行环境

##### 清单 10：测试改造顺序要稳，不要一口气全翻

先按这个顺序补测试：

1. 保住现有同进程测试，确保 builtin 路径不回退
2. 新增 executor 分发单测
3. 新增 runner 成功执行单测
4. 新增 runner 超时 / 非法 JSON / 缺依赖失败单测
5. 最后再补 Agent 桥接走 runner 的集成测试

现有这些测试文件应该继续保留并复用：

- `apps/api-server/tests/test_plugin_manifest.py`
- `apps/api-server/tests/test_plugin_runs.py`
- `apps/api-server/tests/test_agent_plugin_bridge.py`
- `apps/api-server/tests/test_action_plugin_permissions.py`

##### 清单 11：最小验收标准

做到下面 6 条，才算这轮重构设计可以进入代码实现：

1. 内置插件还能按原路径跑通。
2. 第三方插件执行路径已经不要求主进程直接 import 第三方模块。
3. `execute_plugin()` 已经变成统一分发入口。
4. Agent 桥、数据同步链路、动作权限链路都还能继续复用。
5. 第三方依赖不再要求装进主 API 环境。
6. 没有把自动安装、沙箱、多容器这些范围偷偷塞进来。

### 最终检查

- [ ] 3.2 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这份 Spec 真能支撑后续实现和外部接入，不是只会讲方向。
  - 做完你能看到什么：后面可以基于这份 Spec 分阶段做注册表能力和插件市场对接。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/开发者文档/插件开发/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不继续追加前端市场页面实现细节。
  - 怎么算完成：
    1. 需求、设计、任务、示例能一一对上
    2. 后续接手的人能直接知道下一步怎么开发
    3. 明确不做项写清楚，没有偷塞范围
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
