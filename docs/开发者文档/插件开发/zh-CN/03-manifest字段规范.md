# 03-manifest字段规范

## 文档元数据

- 文档目的：明确 `manifest.json` 的字段定义、硬约束、推荐写法和当前实现边界，避免开发者靠猜。
- 当前版本：v1.2
- 关联文档：`docs/开发者文档/插件开发/zh-CN/01-插件开发总览.md`、`docs/开发者文档/插件开发/zh-CN/02-插件开发环境与本地调试.md`、`docs/开发者文档/插件开发/zh-CN/04-插件目录结构规范.md`、`apps/api-server/app/modules/plugin/schemas.py`
- 修改记录：
  - `2026-03-13`：创建首版 manifest 字段规范。
  - `2026-03-13`：调整为按阅读顺序编号，并补充文档元数据。
  - `2026-03-14`：新增 `locale-pack` 类型和 `locales` 字段说明。
  - `2026-03-14`：补充地区上下文读取声明和地区 provider 运行字段。

这份文档就是把 `manifest.json` 说透，不让开发者靠猜。

这里的规则优先对齐当前仓库已经实现的校验逻辑，主要来源是：

- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/plugins/builtin/` 里的现有内置插件

这里顺手再把边界说死：

- `manifest.json` 负责声明插件是什么、入口在哪、风险多高
- 它不负责替代后台任务模型
- 对外执行现在默认先创建 `plugin_job`，而不是根据 `manifest` 直接同步跑完整插件

## 1. 第一版最小示例

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

注意：`description`、`vendor` 现在是规范建议字段，不是现有运行时硬校验字段。你可以先写上，后续注册表和市场都会用到。

如果插件需要正式读取家庭地区上下文，可以再补一段：

```json
{
  "capabilities": {
    "context_reads": {
      "household_region_context": true
    }
  }
}
```

## 2. 字段逐项说明

### `id`

- 必填
- 类型：`string`
- 规则：只能包含小写字母、数字和中划线
- 建议：直接拿它做目录名、注册表主键和仓库 slug 的基础

合格示例：

- `health-basic-reader`
- `homeassistant-device-sync`

不合格示例：

- `HealthBasicReader`
- `health_basic_reader`
- `健康插件`

### `name`

- 必填
- 类型：`string`
- 规则：去掉首尾空格后不能为空
- 建议：一句人能看懂的展示名，不要写内部代号

### `version`

- 必填
- 类型：`string`
- 规则：去掉首尾空格后不能为空
- 建议：用 semver，比如 `0.1.0`

### `types`

- 必填
- 类型：`string[]`
- 规则：至少 1 个；不能重复；只能是这 5 个值：
  - `connector`
  - `memory-ingestor`
  - `action`
  - `agent-skill`
  - `locale-pack`

其中前 4 个是可执行插件类型，`locale-pack` 是语言包插件类型。

它的边界也要说死：

- `locale-pack` 不走 worker，不创建后台执行任务
- 它的作用只是把语言元数据和文案资源注册进系统
- 比如繁体中文这种界面文案扩展，就应该用它，不要硬塞进 `action` 或 `agent-skill`

### `permissions`

- 必填
- 类型：`string[]`
- 规则：允许空数组；不能有空字符串；不能重复
- 建议：只声明运行所需的最小权限

现有插件里能看到的例子：

- `health.read`
- `device.read`
- `device.control`
- `memory.write.device`
- `memory.write.observation`

### `risk_level`

- 必填
- 类型：`string`
- 允许值：`low` / `medium` / `high`

现有行为边界：

- `low`：普通读数据插件常见
- `medium`：普通设备动作插件常见
- `high`：门锁这类高风险动作会触发人工确认入口

### `triggers`

- 必填
- 类型：`string[]`
- 规则：允许空数组；不能有空字符串；不能重复
- 第一版建议值：`manual`、`schedule`、`agent`

这里先写可控触发，不要发明一堆系统还没支持的自动触发语义。

### `entrypoints`

- 对可执行插件必填；纯 `locale-pack` 插件可以留空对象
- 类型：`object`
- 规则：值必须是“模块路径 + 函数名”，而且能被真实 import 到
- 规则：你声明了什么可执行类型，这里就必须给对应入口

支持的 key：

- `connector`
- `memory_ingestor` 或 `memory-ingestor`
- `action`
- `agent_skill` 或 `agent-skill`

文档里推荐统一写下划线 key，因为运行时最终也会归一成下划线。

合格示例：

```json
{
  "connector": "app.plugins.builtin.health_basic.connector.sync",
  "memory_ingestor": "app.plugins.builtin.health_basic.ingestor.transform"
}
```

不合格示例：

```json
{
  "connector": "health_basic_connector",
  "memory_ingestor": "app.plugins.builtin.health_basic.ingestor"
}
```

第一个少了函数名，第二个也少了函数名。

### `locales`

- 只有 `locale-pack` 插件可用
- 类型：`object[]`
- 规则：声明了 `locale-pack` 就至少要有 1 个 locale

每一项至少包含：

- `id`：语言 id，比如 `zh-TW`
- `label`：给通用界面或后台展示用的语言名，比如 `Traditional Chinese`
- `native_label`：给用户看的本地名称，比如 `繁體中文`
- `resource`：语言资源相对路径，比如 `locales/zh-TW.json`
- `fallback`：可选，缺失翻译时要回退到哪个语言，比如 `zh-CN`

最小示例：

```json
{
  "types": ["locale-pack"],
  "entrypoints": {},
  "locales": [
    {
      "id": "zh-TW",
      "label": "Traditional Chinese",
      "native_label": "繁體中文",
      "resource": "locales/zh-TW.json",
      "fallback": "zh-CN"
    }
  ]
}
```

再把冲突规则说清楚，别靠猜：

- 如果同一个家庭里有多个语言包都声明同一个 `locale id`
- 系统不会把它们全部同时暴露给前端
- 只会选一个生效，优先级是：`builtin > official > third_party`
- 如果来源级别一样，就按 `plugin_id` 稳定排序，字典序更小的那个生效
- 被压下去的插件不会报废，但会出现在接口的 `overridden_plugin_ids` 里

说白了，第三方插件不要指望去覆盖内置 `zh-TW`。你真要换文案，要么改内置包，要么换一个新的 locale id。

### `description`

- 选填，但强烈建议填写
- 类型：`string`
- 用途：给维护者和后续市场看

建议写法：

- 这个插件解决什么问题
- 它读什么数据，或者执行什么动作
- 它明确不做什么

### `vendor`

- 选填，但强烈建议填写
- 类型：`object`
- 建议至少有：`name`、`contact`

第一版不强制结构冻结，但必须让人能联系到维护者。

### `capabilities`

- 选填
- 类型：`object`
- 用途：声明插件要读取哪些受控上下文，以及是否要把自己当成地区 provider 挂进系统

当前正式可用的有两项：

- `context_reads.household_region_context: true`
- `region_provider.*`

写了这项以后，系统会在插件执行时把家庭地区上下文放进 `payload._system_context.region.household_context`。

这一项不是让插件直接查数据库，而是走正式入口：

- 受控入口名：`region.resolve_household_context`

示例：

```json
{
  "capabilities": {
    "context_reads": {
      "household_region_context": true
    }
  }
}
```

如果你要把插件当成第三方地区 provider 真正挂进系统，还要再写一组字段：

- `capabilities.region_provider.provider_code`
- `capabilities.region_provider.country_codes`
- `capabilities.region_provider.entrypoint`
- `capabilities.region_provider.reserved`

这组字段现在不是摆设，运行时会真的用到：

- `provider_code`：这个 provider 的正式编码
- `country_codes`：这个 provider 支持哪些国家代码
- `entrypoint`：主服务调用 provider 的入口函数
- `reserved`：`false` 表示这不是预留声明，而是真的要运行

最小可运行示例：

```json
{
  "types": ["region-provider"],
  "entrypoints": {
    "region_provider": "plugin.region_provider.handle"
  },
  "capabilities": {
    "region_provider": {
      "provider_code": "plugin.jp-sample",
      "country_codes": ["JP"],
      "entrypoint": "plugin.region_provider.handle",
      "reserved": false
    }
  }
}
```

这套写法现在已经能跑，但有几条硬规则：

- `types` 里必须包含 `region-provider`
- `entrypoints.region_provider` 必须和 `capabilities.region_provider.entrypoint` 一致
- `country_codes` 至少要有一个值
- 第三方 provider 仍然走 runner 子进程，不直接进主进程

## 3. 类型和入口最小对照

| 类型 | 推荐模块 | 推荐函数 | 说明 |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | 读取外部原始数据 |
| `memory-ingestor` | `ingestor.py` | `transform` | 原始记录转标准记忆 |
| `action` | `executor.py` | `run` | 执行动作 |
| `agent-skill` | `skill.py` | `run` | 暴露给 Agent 的受控能力 |
| `locale-pack` | `locales/*.json` | 无 | 注册界面语言和文案资源 |

## 4. 跟现有实现直接相关的硬约束

这些不是建议，是不满足就会出问题：

1. `id` 不能重复，插件注册中心会拒绝重复插件 id。
2. `manifest.json` 顶层必须是对象，不能是数组。
3. 可执行插件的 `entrypoints` 指到的函数必须可调用。
4. `types` 中每一种可执行能力都必须有对应入口；`locale-pack` 不需要 Python 入口。
5. Agent 统一入口当前只允许 `connector` 和 `agent-skill`。
6. `action` 插件还要额外过权限检查；高风险动作还要人工确认。
7. `locale-pack` 至少要声明一个 `locales` 项，而且 `resource` 必须是插件目录内的相对路径。
7. 如果插件要读家庭地区上下文，必须显式声明 `capabilities.context_reads.household_region_context=true`。
8. 如果插件要作为地区 provider 运行，必须显式声明 `types=["region-provider"]` 和完整的 `capabilities.region_provider`。

## 5. 第一版先不要写进 manifest 的东西

这些东西现在看起来高级，实际上会把边界搞烂：

- 远程安装地址
- 自动下载脚本
- 沙箱策略配置
- 全量签名验证字段
- 市场前端展示布局元数据
- 把 `reserved=true` 的地区 provider 宣传成“已经接管系统地区目录”的误导字段

一句话：先把运行声明写清楚，不要把还没实现的开放平台概念硬塞进去。

## 6. 开发者提交前自检

1. `id` 是否满足字符规则？
2. `types` 是否只用了当前支持的 5 类？
3. 如果是可执行插件，`entrypoints` 是否每一项都能 import 到真实函数？
4. `permissions` 是否最小化，而不是乱申请？
5. `risk_level` 是否和插件真实风险匹配？
6. 如果是 `action`，是否已经明确风险和权限边界？
7. 如果是 `locale-pack`，是否已经提供 `locales/*.json` 这类真实资源文件，并写清回退语言？
8. 有没有偷偷依赖远程安装、远程执行、沙箱、签名平台？

如果你声明的 locale id 跟现有内置语言重复，也要先想清楚：你大概率不会生效。

这些都过了，再去准备注册表材料。
