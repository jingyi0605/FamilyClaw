# GitHub Actions 工作流说明

## 这套工作流现在负责什么

这套自动化现在不是只会“从 Issue 生成一个 PR 草案”了，而是拆成两条清楚的链：

1. `plugin-submission.yml`
   负责把收录 Issue 变成校验结果和机器人 PR。
2. `plugin-submission-review.yml`
   负责跟踪 PR 的审核状态，把 PR / Issue 的标签和说明同步起来，并在仓库允许时尝试开启自动合并。

这样分开有个好处：提交流程和审核流程各做各的事，不会把所有逻辑糊在一个 workflow 里。

## 第一条链：Issue -> 校验 -> 机器人 PR

`plugin-submission.yml` 负责这些步骤：

1. 确保市场仓库所需标签存在
2. 读取插件收录 Issue
3. 调用脚本校验插件仓库
4. 生成 `plugins/<plugin_id>/entry.json`
5. 创建或更新机器人 PR
6. 回写 Issue 状态和校验结果

关键边界：

- 只会改 PR 分支，不会直接改默认分支
- 校验失败不会生成正式条目
- 同一个 Issue 复用同一个自动化 PR

## 第二条链：PR 审核状态同步

`plugin-submission-review.yml` 负责这些步骤：

1. 监听插件收录 PR 的打开、更新、关闭、审核提交和审核撤销
2. 根据审核结果切换 PR 标签
3. 把对应 Issue 状态同步成“待审核 / 要求修改 / 已批准 / 已拒绝”
4. 审核通过时，尝试开启 GitHub Auto-merge

注意，这里只是“尝试开启自动合并”。

真正能不能合并，最后还是由这些 GitHub 规则决定：

- 分支保护
- 审批数量要求
- Code Owner 审核要求
- 仓库是否允许 Auto-merge

## 必要仓库权限

仓库至少要给 GitHub Actions 这些权限：

- `contents: write`
- `pull-requests: write`
- `issues: write`

仓库设置里还必须打开：

- `Read and write permissions`
- `Allow GitHub Actions to create and approve pull requests`
- `Allow auto-merge`

少一个，流程都会残。

## 现在的审批边界

这套实现明确坚持一条边界：

机器人可以生成 PR、同步状态、尝试开启自动合并，但不能替维护者决定“这个插件值不值得收录”。

真正的批准动作，仍然应该来自：

- 维护者审核
- `CODEOWNERS`
- 分支保护规则

## 验收时要看什么

至少看下面这些现象有没有出现：

1. 新建收录 Issue 后，标签会自动补齐
2. 校验通过后，会生成或更新机器人 PR
3. PR 会自动请求审核人
4. 审核人要求修改后，Issue 会自动切到“等待作者补充”
5. 审核通过后，PR / Issue 会自动切到“已批准”
6. 仓库允许 Auto-merge 时，workflow 会尝试开启自动合并

## 一句实话

这套流程真正难的不是“写一个 YAML”，而是把自动化边界守住：

- 该自动的自动
- 不该自动拍板的，别让机器人越权
