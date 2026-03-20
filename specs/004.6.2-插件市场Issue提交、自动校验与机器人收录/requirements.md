# 需求文档 - 插件市场 Issue 提交、自动校验与机器人收录

状态：Draft

## 简介

当前市场仓库已经有正式目录结构：

- `market.json`
- `plugins/<plugin_id>/entry.json`

但第三方插件要进入市场，还是默认要求作者自己改注册表仓库、自己提 PR。

这对熟悉 GitHub 流程的人不是大问题，但对普通开发者来说门槛还是太高：

- 不知道条目字段怎么填
- 不知道哪些字段应该抄，哪些字段应该自动生成
- 不知道插件仓库本身是否满足市场要求
- 提交材料不完整时，也没有自动反馈

如果继续让提交方直接改条目，维护者就会被一堆低质量 PR 拖死。

这份 Spec 要解决的真问题是：

把“插件申请进入市场”的入口统一成 Issue，再用自动校验和机器人生成 PR 的方式，把重复劳动拿掉，但不破坏人工审核这条底线。

## 术语表

- **System**：FamilyClaw 插件市场仓库自动收录链路。
- **收录 Issue**：第三方作者在市场仓库里提交的插件收录申请。
- **Issue Form**：GitHub Issue 模板，负责收集插件仓库地址、基本信息和补充说明。
- **校验工作流**：GitHub Actions 或等价自动流程，用来检查 Issue 和插件仓库是否合法。
- **机器人 PR**：由自动流程生成或更新的市场条目 PR。
- **正式市场条目**：已经合并进市场仓库的 `plugins/<plugin_id>/entry.json`。

## 范围说明

### In Scope

- 定义插件收录 Issue Form 字段
- 定义插件仓库自动校验规则
- 定义从 Issue 生成市场条目的规则
- 定义机器人创建或更新 PR 的流程
- 定义人工审核边界、失败反馈和重试方式
- 定义市场仓库里与自动收录相关的脚本和工作流结构

### Out of Scope

- 直接跳过 PR，把 Issue 自动写进 `main`
- 自动修改所有 FamilyClaw 实例的市场源配置
- 自动批准高风险插件进入市场
- 非 GitHub 仓库来源的自动收录
- 市场内支付、签名、评分、信誉体系

## 需求

### 需求 1：第三方作者可以通过 Issue 提交插件收录申请

**用户故事：** 作为第三方开发者，我希望通过一个明确的 Issue 表单提交插件收录申请，以便我不用先学会市场仓库的目录结构和条目格式。

#### 验收标准

1. WHEN 第三方作者打开市场仓库 THEN System SHALL 提供正式的插件收录 Issue Form。
2. WHEN 作者填写 Issue Form THEN System SHALL 要求提供最小必要字段，而不是只留一个自由文本框。
3. WHEN 作者漏填关键字段 THEN System SHALL 在提交阶段或校验阶段明确指出缺什么。

### 需求 2：系统必须自动校验插件仓库和关键元数据

**用户故事：** 作为维护者，我希望机器人先帮我检查插件仓库和 `manifest.json`，以便我不用手工筛掉大量明显不合格的申请。

#### 验收标准

1. WHEN 收录 Issue 创建或更新 THEN System SHALL 自动检查插件仓库是否可访问。
2. WHEN 插件仓库可访问 THEN System SHALL 自动检查 `manifest.json`、README、版本信息和必要安装信息。
3. WHEN 关键校验失败 THEN System SHALL 在 Issue 或检查结果里明确反馈失败原因，而不是只给一句 workflow failed。
4. WHEN 机器人从插件仓库推导市场版本 THEN System SHALL 优先依据仓库里的 release / tag 生成 `versions[]`，而不是让作者在 Issue 文本里手填版本矩阵。
5. WHEN 市场条目保留多个版本 THEN System SHALL 为每个版本分别读取对应 tag 下的 `manifest.json`，并写入该版本自己的 `min_app_version`。

### 需求 3：系统必须自动生成或更新市场条目 PR

**用户故事：** 作为维护者，我希望机器人能把通过校验的 Issue 转成可审核的 PR，以便我审核内容而不是手写 JSON。

#### 验收标准

1. WHEN 收录 Issue 通过自动校验 THEN System SHALL 生成或更新 `plugins/<plugin_id>/entry.json`。
2. WHEN 同一个 Issue 被补充信息后重新触发 THEN System SHALL 更新对应机器人 PR，而不是重复创建一堆 PR。
3. WHEN 机器人生成 PR THEN System SHALL 在 PR 和 Issue 之间建立清楚的互相引用。
4. WHEN 条目包含多个版本 THEN System SHALL 把这些版本保存在同一个 `entry.json` 的 `versions[]`，并保证 `latest_version` 指向当前最高版本。

### 需求 4：市场条目必须坚持“自动生成为主，人工补充为辅”

**用户故事：** 作为维护者，我希望能自动生成大部分市场条目字段，但仍保留少量人工判断空间，以便减少重复劳动又不丢审核控制。

#### 验收标准

1. WHEN 字段可以从插件仓库直接推导 THEN System SHALL 优先自动生成，而不是要求 Issue 重复填写同一份信息。
2. WHEN 字段属于市场运营判断，例如分类补充或审核说明 THEN System SHALL 允许在 Issue 或 PR 审核阶段人工调整。
3. WHEN 自动生成内容和插件仓库事实不一致 THEN System SHALL 拒绝生成正式条目或将其标记为待人工处理。

### 需求 5：系统必须保留人工审核和合并边界

**用户故事：** 作为项目维护者，我希望自动化只负责提案，不负责最终上架，以便避免恶意或低质量插件直接进入市场。

#### 验收标准

1. WHEN 收录 Issue 已通过自动校验 THEN System SHALL 创建机器人 PR，而不是直接修改默认分支。
2. WHEN 机器人 PR 尚未合并 THEN System SHALL 不把该插件视为正式市场条目。
3. WHEN 维护者拒绝收录 THEN System SHALL 允许关闭 Issue 和 PR，并保留拒绝原因。

### 需求 6：系统必须能清楚反馈失败、补充和重试状态

**用户故事：** 作为第三方开发者，我希望知道当前卡在哪、还差什么，以便我能自己补齐，而不是反复问维护者。

#### 验收标准

1. WHEN 自动校验失败 THEN System SHALL 明确区分是 Issue 字段缺失、仓库不可访问、`manifest` 不合法还是安装信息不完整。
2. WHEN 作者按要求补充 Issue 后重新触发 THEN System SHALL 支持重新校验，而不是要求重新开一个新 Issue。
3. WHEN 自动流程因为 GitHub 限流或临时错误失败 THEN System SHALL 区分“系统异常”和“插件不合格”。

### 需求 7：官方市场默认源和用户实例配置不能被这条流程偷偷改动

**用户故事：** 作为平台维护者，我希望市场收录流程只影响市场仓库内容，而不是顺手改动部署实例的市场源配置，以便守住信任边界。

#### 验收标准

1. WHEN 插件收录 Issue 被处理 THEN System SHALL 只影响市场仓库条目和相关 PR，不自动改动 FamilyClaw 实例的市场源列表。
2. WHEN 插件进入官方市场 THEN System SHALL 通过现有市场同步链路被实例看见，而不是靠额外配置注入。
3. WHEN 用户要接入第三方市场 THEN System SHALL 继续要求用户显式添加第三方市场源。

### 需求 8：系统必须定时发现已收录插件的新版本并生成审核 PR

**用户故事：** 作为市场维护者，我希望插件已经收录以后，后续 release / tag 能被定时发现并自动生成更新 PR，以便不用每次等作者重提一遍收录 Issue。

#### 验收标准

1. WHEN 已收录插件源码仓库发布新的 tag / release THEN System SHALL 在定时扫描时发现它。
2. WHEN System 发现新的正式版本 tag THEN System SHALL 只读取新增 tag 对应的 `manifest.json`，而不是每轮重扫所有历史版本细节。
3. WHEN System 发现新版本 THEN System SHALL 更新现有 `plugins/<plugin_id>/entry.json` 的 `versions[]` 和 `latest_version`，并创建或更新机器人 PR。
4. WHEN 上游仓库删除旧 tag THEN System SHALL 不自动删除市场里已经存在的历史版本记录。

## 非功能需求

### 非功能需求 1：可理解性

1. WHEN 第三方作者第一次提交收录 Issue THEN System SHALL 让作者看懂要填什么、为什么填、填错会怎样。
2. WHEN 维护者查看机器人结果 THEN System SHALL 能一眼分清“自动校验通过/失败”“等待补充”“等待人工审核”。

### 非功能需求 2：可靠性

1. WHEN GitHub Actions 临时失败、网络超时或速率限制出现 THEN System SHALL 不把这些临时问题误判成插件不合格。
2. WHEN 同一个 Issue 被重复编辑和重跑 THEN System SHALL 尽量复用已有 PR 和分支，避免生成重复垃圾结果。

### 非功能需求 3：可维护性

1. WHEN 后续市场条目 schema 扩展 THEN System SHALL 基于统一生成器和校验器扩展，而不是在 workflow 里硬编码一堆字段拼接。
2. WHEN 维护者排查某个收录失败问题 THEN System SHALL 能定位到对应 Issue、自动校验结果、生成 PR 和最终市场条目。

## 成功定义

- 第三方作者可以不用手写 `entry.json`，只靠 Issue 完成插件收录申请。
- 自动流程能检查插件仓库并生成机器人 PR，维护者审核成本显著下降。
- 市场仓库仍然以合并后的条目文件作为唯一事实来源，没有被 Issue 直写主分支破坏。
- 用户实例的市场源信任边界保持不变，收录流程不偷偷改部署配置。
