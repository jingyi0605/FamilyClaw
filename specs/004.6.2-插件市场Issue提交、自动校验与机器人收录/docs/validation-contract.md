# 自动校验输入输出契约

## 这份文档是干什么的

这份文档用来把三件事收口：

1. Issue 解析后长什么样
2. 自动校验输出长什么样
3. 错误回写到 Issue 时该怎么表达

如果这三件事不先定，后面就会出现这种垃圾状态：

- workflow 自己拼一套字段
- 脚本再拼另一套字段
- PR 评论又是第三套说法

最后没人知道哪个结果才是真的。

## 1. Issue 解析结果

建议把 Issue 解析成一个统一对象：`PluginSubmissionIssue`

最小结构如下：

```json
{
  "issue_number": 123,
  "plugin_repo_url": "https://github.com/example/weather-forecast-plugin",
  "plugin_repo_branch": "main",
  "manifest_path": "manifest.json",
  "readme_path": "README.md",
  "package_root": "plugin",
  "requirements_path": "requirements.txt",
  "summary_override": "根据家庭地区提供天气查询和天气提醒。",
  "category_hints": ["生活服务", "天气"],
  "maintainers": [
    {
      "name": "Example Maintainer",
      "url": "https://github.com/example"
    }
  ],
  "maintainer_notes": "当前只提供 source archive 安装方式。"
}
```

### 字段要求

- `issue_number`
  - GitHub Issue 编号
  - 作为后续 PR 关联键的一部分
- `plugin_repo_url`
  - 必填
  - 必须是 GitHub 仓库地址
- `plugin_repo_branch`
  - 可选
  - 没填就按 `main`
- `manifest_path`
  - 可选
  - 没填就按 `manifest.json`
- `readme_path`
  - 可选
  - 没填就按 `README.md`
- `package_root`
  - 可选
  - 没填就按 `plugin`
- `requirements_path`
  - 可选
  - 没填就按 `requirements.txt`
- `summary_override`
  - 可选
  - 用于补市场展示摘要
- `category_hints`
  - 可选
  - 只是建议，不是最终事实来源
- `maintainers`
  - 建议有
  - 最终可进入市场条目
- `maintainer_notes`
  - 可选
  - 仅用于审核，不进入正式条目

## 2. 自动校验输出

自动校验必须输出一个统一对象：`SubmissionValidationResult`

建议结构如下：

```json
{
  "status": "failed",
  "plugin_id": null,
  "field_errors": [
    {
      "field": "plugin_repo_url",
      "error_code": "issue_form_invalid",
      "detail": "插件源码仓库地址不能为空。"
    }
  ],
  "repository_errors": [],
  "generated_entry": null,
  "report_markdown": "## 自动校验失败\n- 缺少插件源码仓库地址"
}
```

### `status` 允许值

- `passed`
  - 自动校验通过，可以继续生成或更新 PR
- `failed`
  - 作者输入或插件仓库不合格，需要作者修
- `system_error`
  - GitHub 限流、网络超时、机器人脚本异常这类系统问题

### `field_errors`

用来表示 Issue 自身的问题，比如：

- 仓库地址缺失
- URL 格式不合法
- 路径为空

### `repository_errors`

用来表示插件仓库本身的问题，比如：

- 仓库不可访问
- `manifest.json` 不存在
- README 不存在
- 版本信息不完整

### `generated_entry`

只有在 `status = passed` 时才应该存在。

它的作用不是直接写入主分支，而是作为生成 `plugins/<plugin_id>/entry.json` 的标准中间结果。

### `report_markdown`

这是给人看的摘要，不是给程序二次解析的真相。

程序应该吃结构化字段，人看 `report_markdown`。

## 3. 错误回写格式

Issue 里的错误反馈必须稳定，不要每次换说法。

建议按三段写：

```markdown
## 自动校验结果

状态：未通过

### 发现的问题

- `plugin_repo_url`：插件源码仓库地址不能为空。
- `manifest_path`：找不到指定的 `manifest.json`。

### 下一步怎么处理

1. 修改当前 Issue 中的错误字段。
2. 使用约定的重跑方式重新触发校验。
```

## 4. PR 侧输出

当自动校验通过并生成 PR 时，PR 里至少要带这些信息：

- 对应 Issue 编号
- 本次自动生成的 `plugin_id`
- 自动生成依据：
  - 插件仓库地址
  - `manifest.json` 路径
  - README 路径
- 仍需人工确认的字段

## 5. 幂等要求

同一个 Issue 多次触发时：

- 应该尽量复用同一个 PR
- 应该覆盖旧的自动生成结果
- 不应该产生多份相互打架的条目草案

这条必须写死，不然市场仓库很快就会被机器人自己制造的垃圾 PR 塞满。

## 一句实话

自动化系统最怕的不是失败，而是“每个环节都说自己成功了，但谁都不是同一套数据”。

所以这份契约的目的只有一个：让解析、校验、生成、回写都围绕同一份结构跑。
