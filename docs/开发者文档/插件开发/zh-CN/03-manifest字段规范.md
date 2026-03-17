# 03-manifest字段规范

## 文档元数据

- 文档目的：把 `manifest.json` 里哪些字段是正式入口、哪些约束是硬规则、哪些细节应该去别处查，说清楚。
- 当前版本：v1.5
- 关联文档：`docs/开发者文档/插件开发/zh-CN/00-文档使用与维护原则.md`、`docs/开发者文档/插件开发/zh-CN/11-插件配置接入说明.md`、`specs/004.2.3-插件配置协议与动态表单/docs/README.md`、`apps/api-server/app/modules/plugin/schemas.py`
- 修改记录：
  - `2026-03-13`：创建首版 manifest 字段规范。
  - `2026-03-14`：补充 `locale-pack`、地区上下文和 `schedule_templates` 规则。
  - `2026-03-16`：补充 `channel`、`region-provider`、正式配置协议入口，并改成“稳定规则 + 事实来源引用”写法。
  - `2026-03-17`：补充 `theme-pack`、`ai-provider`、版本治理字段边界和统一启停规则引用。

这份文档只保留稳定规则，不复制一大坨会频繁变化的字段表。

需要看当前可运行的精确字段形状、配置样例、接口样例时，直接看这些事实来源：

- `apps/api-server/app/modules/plugin/schemas.py`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-manifest-示例.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`

## 0. 2026-03-17 最新边界

这份文档现在要按 `004.5` 的结果理解，不要再按旧口径把主题和 AI 供应商排除在正式插件类型之外。

先记住三件事：

1. 正式插件类型现在是 9 类，不是旧文档里偶尔出现的 7 类。
2. 插件是否可用只认统一状态：`enabled` 和 `disabled_reason`。
3. 版本治理字段要分清谁声明、谁生成：
   - `manifest.json` 负责声明：`version`、`compatibility`
   - 统一插件注册结果负责补充：`installed_version`、`update_state`

插件启停规则统一看：

- `docs/开发设计规范/20260317-插件启用禁用统一规则.md`

## 1. 先说边界

`manifest.json` 负责声明三件事：

- 这个插件是什么
- 这个插件有哪些正式入口
- 这个插件需要哪些运行时声明

它不负责这几件事：

- 不替代后台任务模型
- 不替代页面实现
- 不替代配置实例持久化

对外执行现在默认先创建 `plugin_job`，而不是因为你写了入口函数，就让接口同步把插件跑完。

## 2. 第一版最小示例

```json
{
  "id": "health-basic-reader",
  "name": "健康基础数据插件",
  "version": "0.1.0",
  "types": ["connector", "memory-ingestor"],
  "permissions": [
    "health.read",
    "memory.write.observation"
  ],
  "risk_level": "low",
  "triggers": ["manual", "schedule"],
  "entrypoints": {
    "connector": "app.plugins.builtin.health_basic.connector.sync",
    "memory_ingestor": "app.plugins.builtin.health_basic.ingestor.transform"
  },
  "description": "读取健康原始数据，并转成标准 Observation。",
  "vendor": {
    "name": "FamilyClaw 官方示例",
    "contact": "https://github.com/FamilyClaw"
  }
}
```

如果插件需要正式配置，再补 `config_specs`。如果插件需要读家庭地区上下文，再补 `capabilities.context_reads.household_region_context=true`。

## 3. 字段逐项说明

### `id`

- 必填
- 类型：`string`
- 规则：只能包含小写字母、数字和中划线
- 建议：直接把它当目录名、注册表主键和仓库 slug 的基础

### `name`

- 必填
- 类型：`string`
- 规则：去掉首尾空格后不能为空
- 建议：写人能看懂的展示名，不要写内部代号

### `version`

- 必填
- 类型：`string`
- 规则：去掉首尾空格后不能为空
- 建议：用 semver，比如 `0.1.0`

`version` 是插件声明版本，不是“当前设备上实际安装版本”的别名。

这轮最小版本治理里要分清：

- `version`：插件声明自己是什么版本
- `installed_version`：统一注册结果里看到的已安装版本
- `update_state`：统一注册结果里计算出来的更新状态

不要把 `installed_version` 或 `update_state` 反向写回 `manifest.json`。

### `types`

- 必填
- 类型：`string[]`
- 规则：至少 1 个；不能重复；只能使用当前正式支持的类型

当前已经正式进入体系的类型有：

- `connector`
- `memory-ingestor`
- `action`
- `agent-skill`
- `locale-pack`
- `channel`
- `region-provider`
- `theme-pack`
- `ai-provider`

这里不要再写死成“只有 5 类”或者“只有 4 类”。

边界也别搞混：

- `locale-pack` 负责注册语言资源，不走 worker 执行链
- `channel` 负责通讯平台进出站接入
- `region-provider` 负责地区目录能力，不是普通同步插件换个名字
- `theme-pack` 负责主题资源和主题元数据接入，是正式插件类型，但不是执行类插件
- `ai-provider` 负责 AI 供应商能力声明和配置元数据接入，是正式插件类型，但不是普通动作插件

### `permissions`

- 必填
- 类型：`string[]`
- 规则：允许空数组；不能有空字符串；不能重复
- 建议：只声明运行所需的最小权限

### `risk_level`

- 必填
- 类型：`string`
- 允许值：`low` / `medium` / `high`

### `triggers`

- 必填
- 类型：`string[]`
- 规则：允许空数组；不能有空字符串；不能重复
- 第一版常用值：`manual`、`schedule`、`agent`

这里的 `schedule` 只表示“允许被计划任务系统调用”，不表示“插件自己接管调度器”。

### `schedule_templates`

- 选填
- 类型：`object[]`
- 用途：给计划任务页面提供推荐模板，不会自动给任何家庭建任务

只要声明了 `schedule_templates`，`triggers` 就必须包含 `schedule`。

### `entrypoints`

- 对可执行插件必填
- 类型：`object`
- 规则：值必须是“模块路径 + 函数名”，而且能被真实 import 到
- 规则：声明了什么可执行类型，这里就必须给对应入口

当前常见 key：

- `connector`
- `memory_ingestor` 或 `memory-ingestor`
- `action`
- `agent_skill` 或 `agent-skill`
- `channel`
- `region_provider` 或 `region-provider`

文档里统一推荐写下划线 key，因为运行时最终也会归一到下划线。

### `locales`

- 只有 `locale-pack` 插件可用
- 类型：`object[]`
- 规则：声明了 `locale-pack` 就至少要有 1 个 locale

### `capabilities`

- 选填
- 类型：`object`
- 用途：声明插件要读取哪些受控上下文，或者把自己挂成正式扩展能力

当前这轮已经正式可用的能力声明：

- `context_reads.household_region_context`
- `region_provider.*`

如果是通道插件，平台能力相关声明继续写在通道插件自己的正式字段里，不要再把通道字段散落到页面常量里。

### `config_specs`

- 选填
- 类型：`object[]`
- 用途：声明正式插件配置协议

每一项至少包含：

- `scope_type`
- `schema_version`
- `config_schema`
- `ui_schema`

这轮只支持两个正式作用域：

- `plugin`
- `channel_account`

这里故意不把完整字段类型表、widget 表、显示条件表再抄一遍。那些会变，直接看：

- `docs/开发者文档/插件开发/zh-CN/11-插件配置接入说明.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/README.md`
- `apps/api-server/app/modules/plugin/schemas.py`

稳定规则只有这几条：

1. 字段定义只保留一份来源，也就是插件 manifest。
2. 没有 `config_specs` 的旧插件仍然可以继续展示、启停、执行。
3. secret 字段读取时绝不回显明文。

### `description`

- 选填，但强烈建议填写
- 类型：`string`
- 建议写清楚：
  - 这个插件解决什么问题
  - 它读什么数据，或者执行什么动作
  - 它明确不做什么

### `vendor`

- 选填，但强烈建议填写
- 类型：`object`
- 建议至少有：`name`、`contact`

## 4. 类型和入口最小对照

| 类型 | 推荐模块 | 推荐函数 | 说明 |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | 读取外部原始数据 |
| `memory-ingestor` | `ingestor.py` | `transform` | 原始记录转标准记忆 |
| `action` | `executor.py` | `run` | 执行动作 |
| `agent-skill` | `skill.py` | `run` | 暴露给 Agent 的受控能力 |
| `channel` | `channel.py` | `handle` | 处理通道平台进出站 |
| `region-provider` | `region_provider.py` | `handle` | 提供地区目录能力 |
| `locale-pack` | `locales/*.json` | 无 | 注册界面语言和文案资源 |
| `theme-pack` | 资源清单或主题模块 | 无 | 注册主题资源和主题元数据 |
| `ai-provider` | provider 描述模块或清单 | 无 | 注册 AI 供应商元数据和配置能力 |

## 5. 跟现有实现直接相关的硬约束

这些不是建议，是不满足就会出问题：

1. `id` 不能重复。
2. `manifest.json` 顶层必须是对象。
3. 可执行插件的 `entrypoints` 必须能定位到真实可调用函数。
4. `types` 里每一种可执行能力都必须有对应入口。
5. `locale-pack` 至少要声明一个 `locales` 项。
6. 如果插件要被计划任务系统引用，`triggers` 里必须显式包含 `schedule`。
7. 如果声明了 `schedule_templates`，`triggers` 里也必须包含 `schedule`。
8. 如果插件要读家庭地区上下文，必须显式声明 `capabilities.context_reads.household_region_context=true`。
9. 如果插件要作为地区 provider 运行，必须显式声明 `types=["region-provider"]` 和完整的 `capabilities.region_provider`。
10. 如果插件声明了 `config_specs`，后端会按正式协议校验，不符合协议会直接报错。
11. 没有配置协议的旧插件，不会因为这次新增 `config_specs` 被判成非法插件。

## 6. 第一版先不要写进 manifest 的东西

这些东西现在看起来高级，实际上会把边界搞烂：

- 远程安装地址
- 自动下载脚本
- 沙箱策略配置
- 全量签名验证字段
- 市场页面布局元数据
- 前端页面组件名
- 一整份从后端复制出来的字段表

一句话：先把正式运行声明写清楚，不要把未来可能有、现在还没落地的开放平台概念硬塞进去。

## 7. 开发者提交前自检

1. `id` 是否满足字符规则？
2. `types` 是否只用了当前正式支持的类型？
3. 如果是可执行插件，`entrypoints` 是否每一项都能 import 到真实函数？
4. `permissions` 是否最小化，而不是乱申请？
5. `risk_level` 是否和插件真实风险匹配？
6. 如果用了 `config_specs`，字段定义是否只保留在 manifest，而不是再去页面里写一份常量？
7. 如果用了 secret 字段，是否确认读取不回显、清空走正式语义？
8. 如果要给计划任务系统用，`triggers` 里是不是已经明确写了 `schedule`？
9. 如果是 `channel`，是不是按正式配置协议声明了 `channel_account` 作用域，而不是把字段继续写死在页面？
10. 有没有偷偷依赖远程安装、远程执行、沙箱、签名平台？

这些都过了，再去准备注册表和联调材料。
