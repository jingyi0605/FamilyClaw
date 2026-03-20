# 验收清单

## 目标

确认“收录 Issue -> 自动校验 -> 机器人 PR -> 人工审核 -> 状态同步”这条链已经闭环，不再只是口头约定。

## 提交流程

- [ ] 市场仓库存在正式的 `plugin-submission` Issue Form
- [ ] 新建收录 Issue 后会自动带上 `plugin-submission` 和初始状态标签
- [ ] 自动化会先补齐缺失标签，再开始处理 Issue
- [ ] 自动校验失败时，Issue 会收到明确失败原因
- [ ] 自动校验通过时，会生成或更新 `plugins/<plugin_id>/entry.json`
- [ ] 同一个 Issue 不会重复创建一堆平行 PR

## PR 流程

- [ ] workflow 会创建或更新固定机器人 PR
- [ ] PR 正文里包含对应 Issue 编号和自动生成元数据
- [ ] PR 会自动请求维护者审核
- [ ] PR 带有 `plugin-submission`、`auto-generated` 和审核状态标签

## 审核流程

- [ ] 审核要求修改时，PR 会切到 `status:changes-requested`
- [ ] 审核要求修改时，对应 Issue 会切到 `status:needs-author-fix`
- [ ] 审核通过时，PR 会切到 `status:approved`
- [ ] 审核通过时，对应 Issue 会切到 `status:approved`
- [ ] 仓库允许 Auto-merge 时，workflow 会尝试开启自动合并
- [ ] PR 合并后，Issue 会自动关闭或明确留下已完成结果

## GitHub 设置

- [ ] 仓库已开启 `Read and write permissions`
- [ ] 仓库已开启 `Allow GitHub Actions to create and approve pull requests`
- [ ] 仓库已开启 `Allow auto-merge`
- [ ] 默认分支已开启 “必须走 PR + 必须审批 + 必须 Code Owner 审核”
- [ ] `CODEOWNERS` 和 workflow 里的 `reviewers` 指向真实维护者

## 已知边界

- 这套流程只处理市场仓库收录，不自动修改 FamilyClaw 实例里的市场源配置
- 这套流程不允许绕过 PR 直接改默认分支
- 机器人只能辅助流转，不能替维护者拍板是否正式收录
