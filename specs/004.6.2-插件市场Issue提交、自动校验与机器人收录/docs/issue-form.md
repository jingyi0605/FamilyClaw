# 插件收录 Issue Form 说明

## 这份文档是干什么的

这份文档回答一个最实际的问题：

第三方作者提“插件收录申请” Issue 时，到底要填什么，哪些必须填，哪些不要乱填。

目标很简单：

- 让作者少猜
- 让机器人有稳定输入
- 让维护者少看垃圾 Issue

## Issue Form 应该收哪些字段

### 1. 插件源码仓库地址

- 字段名建议：`plugin_repo_url`
- 必填：是
- 作用：机器人用它去拉插件仓库、检查 `manifest.json` 和 README

要求：

- 必须是公开可访问的 GitHub 仓库地址
- 不接受任意下载链接
- 不接受压缩包直链代替源码仓库

示例：

```text
https://github.com/example/weather-forecast-plugin
```

### 2. 默认分支

- 字段名建议：`plugin_repo_branch`
- 必填：否
- 默认值：`main`

这个字段只用来告诉机器人去哪个分支找 `manifest.json` 和 README。

### 3. `manifest.json` 路径

- 字段名建议：`manifest_path`
- 必填：否
- 默认值：`manifest.json`

如果插件仓库不是把 `manifest.json` 放在根目录，就必须明确写出来。

### 4. README 路径

- 字段名建议：`readme_path`
- 必填：否
- 默认值：`README.md`

README 不是装饰品。没有 README，维护者没义务猜这个插件到底干什么。

### 5. 市场摘要补充

- 字段名建议：`summary_override`
- 必填：否

这个字段是给作者补一段“面向市场展示”的摘要，不是让作者把 README 全贴上来。

建议限制：

- 一两句话说清楚用途
- 不要写营销废话
- 不要重复插件名

### 6. 分类建议

- 字段名建议：`category_hints`
- 必填：否

分类可以给建议，但不保证最后一定按作者建议收录。

### 7. 维护者信息

- 字段名建议：`maintainers`
- 必填：建议是

至少要能让维护者知道：

- 谁在维护
- 出问题找谁

### 8. 补充说明

- 字段名建议：`maintainer_notes`
- 必填：否

这里只放真正对审核有帮助的补充信息，比如：

- 依赖哪个外部平台
- 是否只有 release asset 安装方式
- 某些字段为什么要人工覆盖

### 9. 插件包根目录

- 字段名建议：`package_root`
- 必填：建议是
- 默认值：`plugin`

这个字段用来告诉市场安装器，真正的插件包代码放在哪个目录。

### 10. `requirements.txt` 路径

- 字段名建议：`requirements_path`
- 必填：建议是
- 默认值：`requirements.txt`

市场安装不是只看 `manifest.json`。依赖文件也必须能定位到。

## Issue Form 不该收什么

这些东西别塞进表单，不然作者和维护者都会被烦死：

- 让作者手写完整 `entry.json`
- 让作者重复填写 `manifest.json` 里已经有的所有字段
- 让作者贴大段 README 全文
- 让作者上传 ZIP 包
- 让作者填写“请给我通过”这种空话

## 推荐的 Form 结构

建议按下面的顺序组织：

1. 插件仓库地址
2. 分支
3. `manifest.json` 路径
4. README 路径
5. 插件包根目录
6. `requirements.txt` 路径
7. 市场摘要补充
8. 分类建议
9. 维护者信息
10. 补充说明
11. 勾选确认

最后必须有确认项，至少包括：

- 我确认仓库公开可访问
- 我确认 `manifest.json` 和 README 已准备好
- 我确认插件权限和风险声明不是乱填的

## 机器人预期能从 Form 里拿到什么

Issue Form 不需要解决所有事情，它只要给机器人稳定入口就够了。

机器人至少应该能从里面提取出：

- 插件仓库地址
- 仓库分支
- `manifest.json` 路径
- README 路径
- 插件包根目录
- `requirements.txt` 路径
- 少量人工补充字段

剩下这类字段应该优先从插件仓库自动读：

- `plugin_id`
- `name`
- 权限
- 风险等级
- 版本信息

## 一句实话

Issue Form 的目的不是让作者把市场条目重新抄一遍。

它只负责补齐“机器人没法自己猜”的那一小部分信息。越想让作者多填，最后越会变成垃圾入口。
