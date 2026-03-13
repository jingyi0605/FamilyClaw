# 03-manifest字段规范

## 文档元数据

- 文档目的：明确 `manifest.json` 的字段定义、硬约束、推荐写法和当前实现边界，避免开发者靠猜。
- 当前版本：v1.1
- 关联文档：`docs/开发者文档/插件开发/zh-CN/01-插件开发总览.md`、`docs/开发者文档/插件开发/zh-CN/02-插件对接方式说明.md`、`docs/开发者文档/插件开发/zh-CN/04-插件目录结构规范.md`、`apps/api-server/app/modules/plugin/schemas.py`
- 修改记录：
  - `2026-03-13`：创建首版 manifest 字段规范。
  - `2026-03-13`：调整为按阅读顺序编号，并补充文档元数据。

这份文档就是把 `manifest.json` 说透，不让开发者靠猜。

这里的规则优先对齐当前仓库已经实现的校验逻辑，主要来源是：

- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/plugins/builtin/` 里的现有内置插件

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
- 规则：至少 1 个；不能重复；只能是这 4 个值：
  - `connector`
  - `memory-ingestor`
  - `action`
  - `agent-skill`

别扩新类型。现在仓库不认。

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

- 必填
- 类型：`object`
- 规则：值必须是“模块路径 + 函数名”，而且能被真实 import 到
- 规则：你声明了什么 `types`，这里就必须给对应入口

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

## 3. 类型和入口最小对照

| 类型 | 推荐模块 | 推荐函数 | 说明 |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | 读取外部原始数据 |
| `memory-ingestor` | `ingestor.py` | `transform` | 原始记录转标准记忆 |
| `action` | `executor.py` | `run` | 执行动作 |
| `agent-skill` | `skill.py` | `run` | 暴露给 Agent 的受控能力 |

## 4. 跟现有实现直接相关的硬约束

这些不是建议，是不满足就会出问题：

1. `id` 不能重复，插件注册中心会拒绝重复插件 id。
2. `manifest.json` 顶层必须是对象，不能是数组。
3. `entrypoints` 指到的函数必须可调用。
4. `types` 中每一种能力都必须有对应入口。
5. Agent 统一入口当前只允许 `connector` 和 `agent-skill`。
6. `action` 插件还要额外过权限检查；高风险动作还要人工确认。

## 5. 第一版先不要写进 manifest 的东西

这些东西现在看起来高级，实际上会把边界搞烂：

- 远程安装地址
- 自动下载脚本
- 沙箱策略配置
- 全量签名验证字段
- 市场前端展示布局元数据

一句话：先把运行声明写清楚，不要把还没实现的开放平台概念硬塞进去。

## 6. 开发者提交前自检

1. `id` 是否满足字符规则？
2. `types` 是否只用了当前支持的 4 类？
3. `entrypoints` 是否每一项都能 import 到真实函数？
4. `permissions` 是否最小化，而不是乱申请？
5. `risk_level` 是否和插件真实风险匹配？
6. 如果是 `action`，是否已经明确风险和权限边界？
7. 有没有偷偷依赖远程安装、远程执行、沙箱、签名平台？

这些都过了，再去准备注册表材料。
