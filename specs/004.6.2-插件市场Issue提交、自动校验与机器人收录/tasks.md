# 任务清单 - 插件市场 Issue 提交、自动校验与机器人收录（人话版）

状态：DONE

## 这份文档是干什么的

这份任务清单不是拿来讨论“自动化愿景”的，是拿来把插件市场收录流程从口头约定落成一条能执行的链路：

- 作者知道怎么提
- 机器人知道怎么查
- 维护者知道怎么审
- 市场仓库知道什么时候才算正式收录

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

## 阶段 1：先把 Issue 提交规则和自动化边界钉死

- [x] 1.1 定义插件收录 Issue Form
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：把作者提交插件申请时必须填写的字段写成正式 Issue 模板。
  - 做完你能看到什么：作者不需要猜市场条目格式，只需要按表单填信息。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.3.1「收录 Issue 创建流程」
    - `design.md` §3.3.1「收录 Issue Form」
  - 主要改哪里：
    - 补充文档 `docs/issue-form.md`
    - `README.md`
    - `requirements.md`
    - `design.md`
  - 这一步先不做什么：先不写 PR 创建逻辑，不处理 GitHub 权限细节。
  - 完成内容：
    - 新增 `docs/issue-form.md`，把 Issue Form 应收字段、默认值、必填边界和不该收的字段写清楚了
    - 把“作者不手写完整 `entry.json`”这条边界明确写进补充文档
    - 主文档已经同步收口为“Issue 是收录入口，但不是正式市场结果”
  - 怎么算完成：
    1. Issue 模板字段完整且人能看懂
    2. 必填项和选填项边界清楚
  - 怎么验证：
    - 在 GitHub 仓库预览模板
    - 用一份真实插件样例走填报
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.3.1、§3.3.1

- [x] 1.2 定义自动校验输入和输出格式
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：把 Issue 解析结果、校验结果和错误回写格式统一下来，避免 workflow 和脚本各写各的。
  - 做完你能看到什么：后面不管脚本还是 workflow，都围绕同一套结构跑。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` §3.2「数据结构」
    - `design.md` §5.1「错误类型」
  - 主要改哪里：
    - 补充文档 `docs/validation-contract.md`
    - 补充文档 `docs/validation-rules.md`
    - `design.md`
  - 这一步先不做什么：先不生成 `entry.json`，先把数据结构写稳。
  - 完成内容：
    - 新增 `docs/validation-contract.md`，定义了 `PluginSubmissionIssue` 和 `SubmissionValidationResult`
    - 新增 `docs/validation-rules.md`，把仓库、manifest、README、版本和错误分类规则写清楚了
    - 明确了 `failed` 和 `system_error` 的区分，不再把系统异常甩锅给作者
  - 怎么算完成：
    1. Issue 解析对象和校验结果对象都能明确描述
    2. 错误类型能区分作者输入问题和系统异常
  - 怎么验证：
    - 用样例 Issue 做解析演练
    - 用失败样例检查错误归类
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` §3.2、§5.1、§5.3

### 阶段检查

- [x] 1.3 检查提交流程边界是不是已经站稳
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：确认收录入口、字段和错误反馈已经说清楚，不再往后带着模糊边界乱跑。
  - 做完你能看到什么：后面可以放心开始做机器人脚本和 workflow。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文档
  - 这一步先不做什么：不提前做 PR 生成和仓库安装逻辑。
  - 完成内容：
    - 已补齐 `docs/issue-form.md`、`docs/validation-contract.md`、`docs/validation-rules.md`
    - 已把“不能 Issue 直写 main”“不能自动改实例市场源配置”写成明确边界
    - 当前进入下一阶段时，已经能清楚回答作者怎么提、机器人怎么查、失败怎么回
  - 怎么算完成：
    1. 作者提交入口已经明确
    2. 自动校验输入输出已经明确
    3. 失败反馈方式已经明确
  - 怎么验证：
    - 人工走查
    - 用一份虚拟插件申请表演练
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 6
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.2、§3.3.1、§5.3

---

## 阶段 2：把机器人校验和条目生成主链路做出来

- [x] 2.1 实现插件仓库自动校验器
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：写脚本检查插件仓库是否可访问，`manifest.json`、README 和版本信息是否满足市场要求。
  - 做完你能看到什么：明显不合格的申请会先被机器人挡住。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` §2.3.2「自动校验流程」
    - `design.md` §5.1「错误类型」
  - 主要改哪里：
    - 市场仓库 `scripts/validate_plugin_submission.py`
    - 市场仓库 `scripts/marketplace_submission_lib.py`
    - 市场仓库 `samples/local-plugin-fixture/`
    - 补充文档 `docs/validation-rules.md`
  - 这一步先不做什么：先不创建 PR，不动市场仓库目标文件。
  - 完成内容：
    - 新增 `validate_plugin_submission.py`，支持从 GitHub 事件读取 Issue、校验仓库和生成结构化结果
    - 新增共享库 `marketplace_submission_lib.py`，统一解析 Issue Form、访问 GitHub、构建版本列表和校验条目
    - 新增本地样例插件目录，方便离线演练校验脚本
  - 怎么算完成：
    1. 仓库访问、manifest、README、版本校验都能跑
    2. 失败原因能明确回给作者
  - 怎么验证：
    - 单元测试覆盖成功和失败样例
    - 用真实测试仓库跑一遍
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` §2.3.2、§5.1、§5.3

- [x] 2.2 实现 `entry.json` 自动生成器
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：把 Issue 信息和插件仓库事实合并成正式的市场条目草案。
  - 做完你能看到什么：维护者不再需要手写 `plugins/<plugin_id>/entry.json`。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` §2.3.3「条目生成与 PR 流程」
    - `design.md` §3.2.3「GeneratedMarketplaceEntry」
  - 主要改哪里：
    - 市场仓库 `scripts/issue_to_entry.py`
    - 市场条目 schema
  - 这一步先不做什么：先不管 PR 权限和审核流程。
  - 完成内容：
    - 新增 `issue_to_entry.py`，把校验结果写成 `plugins/<plugin_id>/entry.json`
    - 新增 `schemas/entry.schema.json`，给 `entry.json` 提供结构约束
    - 生成器会同步输出分支名、PR 标题和 commit message，给 workflow 直接复用
  - 怎么算完成：
    1. 自动生成的条目符合市场 schema
    2. 自动生成字段和插件仓库事实一致
  - 怎么验证：
    - 用多份样例仓库生成条目
    - 生成结果走 schema 校验
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` §2.3.3、§3.2.3、§6.1

### 阶段检查

- [x] 2.3 检查“Issue 到条目草案”是不是已经通了
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：确认现在不是只有零散脚本，而是真的能从申请走到条目草案。
  - 做完你能看到什么：下一阶段只差把 GitHub PR 自动化接上。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关脚本和文档
  - 这一步先不做什么：不加审核策略扩展，不加信誉体系。
  - 完成内容：
    - 已补 `samples/plugin-submission-issue.md`
    - 当前仓库可以直接用样例 Issue + 本地样例插件目录跑通“解析 -> 校验 -> 生成条目”链路
  - 怎么算完成：
    1. 一份 Issue 能生成一份条目草案
    2. 校验失败时不会生成脏条目
  - 怎么验证：
    - 集成演练一次完整生成流程
    - 检查失败场景回写
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4、需求 6
  - 对应设计：`design.md` §2.3.2、§2.3.3、§5.3、§6.1

---

## 阶段 3：接上机器人 PR、审核闭环和文档

- [x] 3.1 实现机器人创建或更新 PR
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：让 GitHub Actions 把条目草案写进分支，自动创建或更新机器人 PR。
  - 做完你能看到什么：维护者只看 PR，不再手工建分支和写 JSON。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5、需求 6
    - `design.md` §2.3.3「条目生成与 PR 流程」
    - `design.md` §2.3.5「人工审核与正式收录流程」
  - 主要改哪里：
    - 市场仓库 `.github/workflows/plugin-submission.yml`
    - 市场仓库 `.github/ISSUE_TEMPLATE/`
    - 市场仓库 `.github/pull_request_template.md`
    - 市场仓库 `.github/CODEOWNERS`
    - 补充文档 `docs/github-actions.md`
  - 这一步先不做什么：不做自动合并，不做直接写默认分支。
  - 完成内容：
    - 新增 `plugin-submission.yml` workflow，支持 Issue 新建、编辑和 `/rerun-submission`
    - workflow 已接入 `create-pull-request`，走固定自动化分支
    - 已补 `CODEOWNERS` 和 PR 模板，把审批边界真正闭上
  - 怎么算完成：
    1. 通过校验的 Issue 能生成或更新 PR
    2. 同一 Issue 不会重复创建一堆 PR
  - 怎么验证：
    - 在测试仓库跑 GitHub Actions
    - 多次编辑同一 Issue 检查 PR 复用
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` §2.3.3、§2.3.4、§2.3.5、§6.2

- [x] 3.2 补齐审核说明、作者反馈和最终验收材料
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：把维护者怎么审、作者怎么看反馈、什么时候算正式收录写成能直接执行的说明。
  - 做完你能看到什么：接手的人不用再猜这条流程的操作规则。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/`
  - 主要改哪里：
    - 市场仓库使用说明
    - `docs/github-actions.md`
    - `docs/review-checklist.md`
    - `docs/acceptance-checklist.md`
  - 这一步先不做什么：不追加市场治理新能力。
  - 完成内容：
    - 已补 workflow 说明、审核清单和验收清单
    - 已明确“只改市场仓库，不改实例市场源配置”的边界
  - 怎么算完成：
    1. 作者提交、机器人处理、维护者审核三方说明都齐了
    2. “不会自动改实例市场源配置”这条边界写清楚了
  - 怎么验证：
    - 人工从作者视角和维护者视角各走一遍
  - 对应需求：`requirements.md` 需求 5、需求 6、需求 7
  - 对应设计：`design.md` §2.1、§2.3.5、§4.1、§6.3

- [x] 3.3 补齐多版本条目、tag 与发布归档规则
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：把“一个插件怎么保存多个版本、tag 怎么写、什么时候允许 branch 兜底”写成正式规则，并同步补到校验器和文档里。
  - 做完你能看到什么：市场条目不再只是“能跑”，而是对多版本和 tag 边界有明确硬约束。
  - 先依赖什么：2.2、3.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` §3.2.3「GeneratedMarketplaceEntry」
  - 主要改哪里：
    - 市场仓库 `scripts/marketplace_submission_lib.py`
    - 市场仓库 `schemas/entry.schema.json`
    - 市场仓库 `docs/contributing/plugin-submission.md`
    - `docs/开发者文档/插件开发/zh-CN/`
  - 这一步先不做什么：不强制 release asset，不扩展到签名与制品托管平台。
  - 完成内容：
    - 已把多版本条目固定为单个 `plugins/<plugin_id>/entry.json` 下的 `versions[]`
    - 已明确正式多版本必须来自 tag，`git_ref` 统一为 `refs/tags/<tag>`
    - 已明确 `latest_version` 必须指向最高版本，单版本 branch 仅作为开发态兜底
  - 怎么算完成：
    1. 文档能直接回答“多版本怎么存、tag 怎么写”
    2. 自动校验会拦住不合法的多版本条目
  - 怎么验证：
    - 脚本单测覆盖 tag 规范和 `latest_version` 校验
    - 用样例仓库演练多版本生成结果
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.2.3

### 最终检查

- [x] 3.4 最终检查点
  - 状态：DONE
  - 完成日期：2026-03-20
  - 这一步到底做什么：确认这份 Spec 真能指导实现，不是只有概念图和漂亮话。
  - 做完你能看到什么：Issue、校验、PR、审核、边界这几件事能一一对上。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再加新需求，不偷塞附加能力。
  - 完成内容：
    - 当前 Spec 已有 requirements、design、tasks 和 6 份补充文档
    - 自动化模板文件已落到 `apps/api-server/data/marketplace`
    - 当前剩余风险已经收口为“复制到真实 GitHub 仓库后做一次线上实跑”
  - 怎么算完成：
    1. 任务和需求、设计能对上
    2. 审核边界和自动化边界都写清楚
    3. 后续实现者知道先写什么脚本、后接什么 workflow
  - 怎么验证：
    - 按验收清单逐项核对
    - 人工复盘一遍完整链路
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
