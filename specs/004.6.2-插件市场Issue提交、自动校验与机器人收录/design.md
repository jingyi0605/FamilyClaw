# 设计文档 - 插件市场 Issue 提交、自动校验与机器人收录

状态：Draft

## 1. 概述

### 1.1 目标

- 把插件市场的收录入口从“手写条目 PR”收口成“Issue + 机器人 PR”
- 尽量自动读取插件仓库事实，减少手工重复填写
- 保留人工审核边界，避免自动化直接污染正式市场

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7
- `requirements.md` 需求 8

### 1.3 技术约束

- 市场仓库：GitHub 仓库
- 自动化：GitHub Actions
- 条目事实来源：市场仓库中的 `plugins/<plugin_id>/entry.json`
- 插件事实来源：插件源码仓库中的 `manifest.json`、README、版本信息
- 信任边界：机器人不能直接写默认分支，最终必须经人工审核合并

## 2. 架构

### 2.1 系统结构

这条链路只做一件事：把收录申请变成可审核的 PR。

主流程分五段：

1. 作者提交收录 Issue
2. GitHub Actions 读取 Issue Form
3. 校验器拉取插件仓库并检查关键文件
4. 生成器产出 `entry.json`
5. 机器人创建或更新 PR，等待人工审核

这里故意不把“市场同步到 FamilyClaw 实例”塞进来，因为那已经是 `004.6` 现有链路负责的事情。

已收录插件的后续版本同步，是另一条并行支线：

1. 定时扫描现有 `plugins/*/entry.json`
2. 读取每个条目的 `source_repo`
3. 只检查 release / tag 列表有没有新版本
4. 只有发现新增 tag 时，才读取该 tag 下的 `manifest.json`
5. 更新现有条目并生成版本同步 PR

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| Issue Form | 收集最小申请材料 | 作者填写信息 | 标准化 Issue 内容 |
| Issue Parser | 从 Issue 提取结构化字段 | Issue body / metadata | 结构化申请对象 |
| Repository Validator | 校验插件仓库和关键文件 | 仓库地址、分支、路径 | 校验结果 |
| Entry Generator | 生成市场条目草案 | Issue 字段、manifest、README、版本信息 | `entry.json` 草案 |
| PR Orchestrator | 创建或更新机器人 PR | 条目草案、Issue 编号 | 可审核 PR |
| Version Sync Scanner | 定时发现已收录插件的新版本 | 已收录 `entry.json`、插件仓库 release/tag | 更新后的条目和版本同步 PR |

### 2.3 关键流程

#### 2.3.1 收录 Issue 创建流程

1. 作者在市场仓库选择“插件收录申请” Issue Form。
2. Form 收集插件仓库地址、分支、`manifest` 路径、README、补充说明等字段。
3. Issue 创建后自动打上统一标签，例如 `plugin-submission`、`status:submitted`。
4. 工作流开始执行结构化解析和仓库校验。

#### 2.3.2 自动校验流程

1. 解析 Issue Form，生成标准化申请对象。
2. 校验必要字段是否完整。
3. 检查插件仓库是否可访问。
4. 读取 `manifest.json`。
5. 检查 README、版本、权限、风险、安装信息是否自洽。
6. 输出结构化校验结果，并把失败原因回写到 Issue 或检查日志。

#### 2.3.3 条目生成与 PR 流程

1. 校验通过后，生成标准 `entry.json`。
2. 目标路径固定为 `plugins/<plugin_id>/entry.json`。
3. 如果已有由该 Issue 生成的 PR，则更新原 PR 分支。
4. 如果没有，则创建新分支和新 PR。
5. 在 Issue 中回写 PR 链接、当前状态和下一步操作提示。

#### 2.3.4 作者补充与重跑流程

1. 作者按反馈修改 Issue 内容。
2. 作者通过固定评论命令或标签触发重新校验。
3. 系统复用原 Issue 和原 PR，而不是新建平行结果。
4. 新结果覆盖旧状态，并保留历史日志。

#### 2.3.5 人工审核与正式收录流程

1. 维护者审核机器人 PR。
2. 必要时在 PR 中补小改动，例如分类、摘要文案、审核备注。
3. 合并后，`plugins/<plugin_id>/entry.json` 成为正式市场条目。
4. FamilyClaw 实例仍通过现有市场同步逻辑消费这份结果。

#### 2.3.6 已收录插件版本定时同步流程

1. 定时工作流遍历 `plugins/*/entry.json`。
2. 对每个条目，只读取对应 `source_repo` 的 release/tag 列表。
3. 如果没有新 tag，这个插件本轮直接跳过。
4. 如果发现新 tag，才去读取这个 tag 对应的 `manifest.json`。
5. 把新版本追加进原有 `versions[]`，并重算 `latest_version`。
6. 如果同版本原来只是 branch 兜底记录，而现在有正式 tag，就把这个版本收口为 tag 记录。
7. 生成或更新一个固定的版本同步 PR，等待人工审核。

这条支线故意不做“自动删版本”。上游删 tag，不代表市场应该跟着删历史版本，否则会直接破坏用户已知可回滚版本。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7、8

- `plugin-submission.yml`：Issue Form 定义文件，约束作者提交哪些字段。
- `issue_parser`：把 GitHub Issue 文本转成结构化申请对象。
- `repository_validator`：检查仓库、`manifest`、README 和版本信息。
- `entry_generator`：根据 Issue 和插件仓库事实生成 `entry.json`。
- `pr_orchestrator`：负责创建、更新 PR，并回写 Issue 状态。
- `version_sync_scanner`：负责定时扫描已收录条目对应仓库的 release/tag，并只在发现新版本时补写条目。

### 3.2 数据结构

覆盖需求：1、2、3、4、6、7

#### 3.2.1 `PluginSubmissionIssue`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `issue_number` | integer | 是 | Issue 编号 | GitHub 唯一 |
| `plugin_repo_url` | string | 是 | 插件源码仓库地址 | 必须是合法 GitHub 仓库 |
| `plugin_repo_branch` | string | 否 | 仓库分支 | 默认 `main` |
| `manifest_path` | string | 否 | `manifest.json` 路径 | 默认 `manifest.json` |
| `readme_path` | string | 否 | README 路径 | 默认 `README.md` |
| `summary_override` | string | 否 | 市场摘要补充 | 允许人工提供 |
| `category_hints` | array[string] | 否 | 分类建议 | 可为空 |
| `maintainer_notes` | string | 否 | 额外说明 | 不进入正式条目 |

#### 3.2.2 `SubmissionValidationResult`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `status` | string | 是 | 校验状态 | `passed` / `failed` / `system_error` |
| `plugin_id` | string | 否 | 从 manifest 解析出的插件 ID | 失败时可为空 |
| `field_errors` | array[object] | 否 | 字段级错误 | 用于回写 Issue |
| `repository_errors` | array[object] | 否 | 仓库校验错误 | 用于区分仓库问题 |
| `generated_entry` | object | 否 | 生成的条目草案 | 仅通过时存在 |
| `report_markdown` | string | 是 | 给人看的结果摘要 | 直接回写 Issue/PR |

#### 3.2.3 `GeneratedMarketplaceEntry`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | string | 是 | 插件 ID | 必须与目录名一致 |
| `name` | string | 是 | 展示名 | 优先来自 manifest |
| `summary` | string | 是 | 市场摘要 | 可来自 Issue 补充或仓库说明 |
| `source_repo` | string | 是 | 插件源码仓库地址 | 必须可访问 |
| `manifest_path` | string | 是 | manifest 路径 | 必须存在 |
| `readme_url` | string | 是 | README 地址 | 必须可访问 |
| `publisher` | object | 是 | 发布者信息 | 可从 Issue 和仓库补齐 |
| `categories` | array[string] | 否 | 分类 | 允许人工补充 |
| `risk_level` | string | 是 | 风险等级 | 与 manifest 自洽 |
| `permissions` | array[string] | 是 | 权限声明 | 与 manifest 自洽 |
| `latest_version` | string | 是 | 最新版本 | 必须能在 `versions` 中找到，且必须指向最高版本 |
| `versions` | array[object] | 是 | 可安装版本信息 | 至少一个；所有版本都保存在同一个 `entry.json` 里 |
| `install` | object | 是 | 安装信息 | 满足 `004.6` 现有规则 |
| `maintainers` | array[object] | 否 | 维护者 | 可来自 Issue |

补充死规矩：

1. 正式多版本条目必须来自仓库里的 tag，`git_ref` 统一写成 `refs/tags/<tag>`
2. 没有 tag / release 时，只允许退化成引用 branch 的单版本开发态条目
3. `release_asset` 必须提供 `artifact_url`
4. `source_archive` 可以显式提供 `artifact_url`，也可以由宿主按 `git_ref` 推导
5. 多版本条目的 `min_app_version` 不是插件级一份总值，而是每个版本各自一份；机器人要按每个 tag 读取对应版本的 manifest

### 3.3 接口契约

覆盖需求：1、2、3、4、5、6、7

#### 3.3.1 收录 Issue Form

- 类型：GitHub Issue Form
- 路径或标识：`.github/ISSUE_TEMPLATE/plugin-submission.yml`
- 输入：作者填写的插件仓库地址、分支、路径、补充说明
- 输出：结构固定的 Issue 内容
- 校验：字段完整性、URL 基础格式、是否接受仓库规则说明
- 错误：字段缺失、格式不合法、模板校验失败

#### 3.3.2 自动校验工作流

- 类型：GitHub Actions Workflow
- 路径或标识：`.github/workflows/plugin-submission.yml`
- 输入：Issue opened / edited / labeled / comment command
- 输出：检查结果、Issue 评论、PR 创建或更新结果
- 校验：Issue 标签、事件来源、幂等处理、仓库访问性、manifest 和版本信息
- 错误：Issue 解析失败、仓库拉取失败、生成 PR 失败、GitHub 限流

#### 3.3.3 生成脚本

- 类型：CLI / Script
- 路径或标识：`scripts/issue_to_entry.py`
- 输入：结构化 Issue 数据、插件仓库检查结果
- 输出：`entry.json` 内容、校验报告
- 校验：与市场 schema 一致、与 `manifest` 一致、版本列表自洽
- 错误：字段冲突、条目不完整、自动生成失败

#### 3.3.4 定时版本同步工作流

- 类型：GitHub Actions Workflow
- 路径或标识：`.github/workflows/marketplace-version-sync.yml`
- 输入：定时器、手工 `workflow_dispatch`
- 输出：更新后的 `plugins/<plugin_id>/entry.json`、版本同步 PR、工作流摘要
- 校验：只增量发现新增 tag；只读取新增 tag 的 `manifest.json`；不自动删旧版本
- 错误：GitHub 限流、插件仓库 tag 与 manifest 不一致、PR 创建失败

## 4. 数据与状态模型

### 4.1 数据关系

关系要保持简单：

- 一个收录 Issue 对应一个插件收录申请
- 一个申请最多对应一个活跃机器人 PR
- 一个合并后的 PR 对应一个正式市场条目
- 正式市场条目仍然是市场仓库里的文件，不是 Issue，也不是 PR
- 已收录条目后续可以被版本同步任务更新，但仍然必须通过新的 PR 才能进入默认分支

也就是说，Issue 和 PR 都只是过程数据，`entry.json` 才是最终事实。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `submitted` | 已提交申请 | Issue 创建 | 开始自动校验 |
| `validating` | 自动校验中 | Workflow 运行 | 校验完成 |
| `needs_author_fix` | 需要作者补充 | 校验发现输入或仓库问题 | 作者修改后重跑 |
| `system_error` | 自动系统异常 | GitHub 限流、脚本异常、临时失败 | 重跑成功 |
| `pr_opened` | 已生成机器人 PR | 校验通过且 PR 创建成功 | PR 合并或关闭 |
| `approved` | 审核通过 | PR 合并 | 市场同步消费 |
| `rejected` | 审核拒绝 | Issue/PR 被关闭并写明原因 | 重新提交新申请或重开 |

补充一条版本同步边界：

- 定时扫描发现新版本时，不复用收录 Issue 状态机，而是单独生成版本同步 PR
- 这条 PR 仍然服从分支保护和人工审核，不会绕过审核直接写默认分支

## 5. 错误处理

### 5.1 错误类型

- `issue_form_invalid`：Issue 表单缺少关键字段或格式不合法
- `plugin_repo_unreachable`：插件源码仓库不可访问
- `manifest_invalid`：`manifest.json` 不存在或内容不合法
- `entry_generation_failed`：自动生成市场条目失败
- `pr_sync_failed`：机器人创建或更新 PR 失败
- `automation_system_error`：GitHub 平台异常、限流或临时失败
- `version_sync_failed`：定时扫描发现版本信息冲突，当前不能安全更新市场条目

### 5.2 错误响应格式

```json
{
  "detail": "插件仓库 README.md 不存在。",
  "error_code": "manifest_invalid",
  "field": "readme_path",
  "timestamp": "2026-03-20T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：直接回写 Issue，告诉作者补什么。
2. 业务规则错误：不生成 PR，标记为待作者修复。
3. 外部依赖错误：标记为系统异常，允许重跑。
4. 重试、降级或补偿：
   - 同一 Issue 尽量复用同一 PR
   - 系统异常不关闭申请
   - 未通过校验时不产生正式市场条目

## 6. 正确性属性

### 6.1 属性 1：正式市场事实来源不变

*对于任何* 收录申请，系统都应该满足：只有合并进市场仓库的 `plugins/<plugin_id>/entry.json` 才算正式市场条目。

**验证需求：** 需求 3、需求 5、需求 7

### 6.2 属性 2：自动化不能绕过人工审核

*对于任何* 自动校验通过的 Issue，系统都应该满足：机器人只能创建或更新 PR，不能直接改默认分支。

**验证需求：** 需求 3、需求 5

### 6.3 属性 3：市场收录流程不改实例信任边界

*对于任何* 收录申请，系统都应该满足：该流程只影响市场仓库内容，不自动改动 FamilyClaw 实例的市场源配置。

**验证需求：** 需求 7

### 6.4 属性 4：定时版本同步只做增量追加，不自动删历史版本

*对于任何* 已收录插件，系统都应该满足：定时扫描只能追加新版本或把同版本 branch 记录收口为 tag 记录，不能因为上游删 tag 就自动删除市场中的历史版本。

**验证需求：** 需求 8

## 7. 测试策略

### 7.1 单元测试

- Issue 解析器：字段提取、缺省值、格式错误
- 仓库校验器：仓库可访问性、manifest 合法性、README 存在性
- 条目生成器：由 manifest 和 Issue 生成标准 `entry.json`

### 7.2 集成测试

- 从 Issue 示例到生成 PR 草案的完整脚本流程
- 校验失败时的错误回写和状态更新
- 同一 Issue 重跑时复用已有 PR
- 已收录插件发布新 tag 后，定时任务只补抓新 tag 并更新现有条目

### 7.3 端到端测试

- 模拟一个第三方作者提收录 Issue
- 自动生成 PR
- 人工合并后被市场同步链路消费

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.3.1 | Issue Form 人工走查、模板校验 |
| `requirements.md` 需求 2 | `design.md` §2.3.2、§3.2、§5.1 | 校验器单测、失败样例测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§3.3.2 | 生成器集成测试、PR 创建回放 |
| `requirements.md` 需求 4 | `design.md` §3.2.3、§5.3 | 自动生成字段对比测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.5、§6.2 | 分支保护检查、流程演练 |
| `requirements.md` 需求 6 | `design.md` §2.3.4、§5.1、§5.3 | 重跑和错误反馈测试 |
| `requirements.md` 需求 7 | `design.md` §2.1、§4.1、§6.3 | 人工走查、边界检查 |
| `requirements.md` 需求 8 | `design.md` §2.3.6、§3.3.4、§6.4 | 定时扫描集成测试、版本追加测试 |

## 8. 风险与待确认项

### 8.1 风险

- GitHub Actions 权限不够时，机器人创建 PR 可能失败
- 第三方仓库版本发布方式不统一，自动生成 `versions` 需要明确优先级和兜底边界
- 如果 Issue Form 设计过于复杂，作者照样填不明白
- 已收录插件数量增加后，定时扫描要坚持“先看 tag 列表，只有新增 tag 才抓 manifest”，不能偷懒退化成全量重扫

### 8.2 待确认项

- 机器人是直接用 `GITHUB_TOKEN` 还是单独的 Bot Token
- 作者触发“重新校验”是用评论命令、标签还是重新编辑 Issue
