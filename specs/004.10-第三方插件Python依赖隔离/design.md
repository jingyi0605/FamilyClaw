# 设计文档 - 第三方插件Python依赖隔离

状态：Draft

## 1. 概述

### 1.1 目标

- 为第三方插件建立正式的 Python 依赖隔离模型
- 让安装、升级、启动恢复和执行共享同一套 venv 生命周期
- 从第三方插件运行链路中移除对宿主 `sys.executable` 的默认依赖

### 1.2 覆盖需求

- `requirements.md` 需求 1：安装和升级必须创建插件自己的 venv
- `requirements.md` 需求 2：插件 requirements.txt 必须真的被安装
- `requirements.md` 需求 3：runner 必须使用插件自己的 python_path
- `requirements.md` 需求 4：启动恢复必须能修复插件运行环境
- `requirements.md` 需求 5：开发版插件也必须有明确依赖策略
- `requirements.md` 需求 6：文档和错误语义必须说人话

### 1.3 技术约束

- 后端：Python 3.11
- 插件执行后端：仍然基于现有 `subprocess_runner`
- 数据存储：复用现有 plugin mount / marketplace instance 记录
- 运行环境：不引入新的包管理器，只使用 Python venv + pip
- 目录边界：安装态插件继续留在 `data/plugins/third_party/...`，开发版插件继续留在 `plugins-dev/`

## 2. 架构

### 2.1 系统结构

当前结构：

1. 安装流程落盘插件文件
2. 只检查 `requirements.txt` 在不在
3. 挂载记录把 `python_path` 写成宿主 `sys.executable`
4. runner 执行时只拼 `PYTHONPATH`

目标结构：

1. 安装/升级流程落盘插件文件
2. 创建插件自己的 venv
3. 在插件 venv 中安装 `requirements.txt`
4. 把 mount / marketplace instance 的 `python_path` 写成该 venv 中的 Python
5. runner 执行时只使用这个插件专属 `python_path`
6. 启动恢复时发现 venv 缺失或损坏则自动重建

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `plugin_env_manager` | 创建、校验、修复、删除第三方插件 venv | plugin_root、requirements_path | venv 信息、python_path、安装结果 |
| 安装/升级服务 | 在落盘插件文件后调用环境管理器 | 插件版本目录、manifest、requirements | 已准备好的运行环境 |
| 启动恢复服务 | 检查历史挂载的 venv 是否完整并修复 | plugin_root、python_path | 修复结果或错误 |
| runner 执行器 | 只使用插件自己的 python_path 执行 | mount runner config | 插件执行结果 |
| 文档和错误层 | 向用户解释环境状态和修复建议 | 环境错误 | 人类可读提示 |

### 2.3 关键流程

#### 2.3.1 本地安装 / 市场安装

1. 插件产物落盘到目标版本目录
2. 系统解析 `requirements.txt`
3. 创建目标插件 venv
4. 在该 venv 中执行 `pip install -r requirements.txt`
5. 依赖安装成功后回写 `python_path`
6. 只有整条流程成功，才把插件标记为可执行

#### 2.3.2 升级

1. 下载并解压新版本
2. 为新版本目录创建独立 venv
3. 安装新版本 requirements
4. 切换 mount / marketplace instance 指向新版本的 `python_path`
5. 旧版本保留到升级确认或清理阶段，不混用旧 venv

#### 2.3.3 启动恢复

1. 启动同步扫描安装态第三方插件
2. 读取挂载记录里的 `plugin_root`、`python_path`
3. 如果 `python_path` 缺失、文件不存在、版本目录不匹配，判定为环境损坏
4. 自动重建 venv 并重装依赖
5. 成功则更新记录；失败则保留明确错误状态

#### 2.3.4 开发版插件执行

1. `plugins-dev` 插件首次进入可执行路径时，系统检查其开发版 venv
2. 若不存在则创建开发版 venv，并安装该插件的 `requirements.txt`
3. runner 仍然使用开发版插件自己的 `python_path`
4. 不再默认 fallback 到宿主解释器

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6

- `PluginPythonEnvManager`：统一管理第三方插件 venv 生命周期
- `PluginPythonEnvSpec`：描述某个插件运行环境的位置、解释器路径、requirements 路径和状态
- `PluginEnvBootstrapService`：给安装、升级和启动恢复入口复用的环境准备封装
- `PluginEnvHealthCheck`：校验 `python_path`、venv 目录和 requirements 安装结果

### 3.2 数据结构

覆盖需求：1、3、4、5

#### 3.2.1 `PluginPythonEnvSpec`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_root` | `str` | 是 | 插件版本目录或开发源码目录 | 必须存在 |
| `venv_dir` | `str` | 是 | 插件独立 venv 目录 | 由系统维护 |
| `python_path` | `str` | 是 | venv 内 Python 可执行文件路径 | 不允许指向宿主解释器 |
| `requirements_path` | `str` | 是 | 插件 requirements 文件 | 必须存在 |
| `install_mode` | `str` | 是 | `local/marketplace/dev` | 用于区分策略 |
| `status` | `str` | 是 | `ready/building/broken/failed` | 环境状态 |

#### 3.2.2 `PluginEnvPrepareResult`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `python_path` | `str` | 是 | 准备好的插件解释器路径 | 指向 venv |
| `venv_dir` | `str` | 是 | venv 目录 | 必须存在 |
| `installed_packages` | `list[str]` | 否 | 已安装依赖摘要 | 用于日志和排障 |
| `requirements_hash` | `str` | 否 | 当前 requirements 摘要 | 用于判断是否需要重装 |
| `status` | `str` | 是 | `ready` 或 `failed` | 明确结果 |

### 3.3 接口契约

覆盖需求：1、2、3、4、5、6

#### 3.3.1 `prepare_plugin_python_env(...)`

- 类型：Function
- 路径或标识：`app.modules.plugin.env_manager.prepare_plugin_python_env`
- 输入：`plugin_root`、`requirements_path`、`install_mode`
- 输出：`PluginEnvPrepareResult`
- 校验：目录和 requirements 必须存在；目标路径必须在允许范围内
- 错误：`plugin_env_prepare_failed`、`plugin_requirements_missing`、`plugin_python_missing`

#### 3.3.2 `repair_plugin_python_env(...)`

- 类型：Function
- 路径或标识：`app.modules.plugin.env_manager.repair_plugin_python_env`
- 输入：历史 mount / instance 记录
- 输出：修复后的 `PluginEnvPrepareResult`
- 校验：插件根目录仍然存在；损坏原因可识别
- 错误：`plugin_env_repair_failed`

#### 3.3.3 `validate_plugin_python_env(...)`

- 类型：Function
- 路径或标识：`app.modules.plugin.env_manager.validate_plugin_python_env`
- 输入：`plugin_root`、`python_path`、`requirements_path`
- 输出：健康状态、问题列表
- 校验：检查 `python_path` 是否位于 venv，文件是否存在
- 错误：不直接抛业务异常，返回结构化校验结果

## 4. 数据与状态模型

### 4.1 数据关系

当前数据库里已经有：

- `plugin_root`
- `manifest_path`
- `python_path`
- `working_dir`

这次不一定需要新增表，但必须重新定义这些字段的语义：

- `python_path` 不再等于宿主 `sys.executable`
- 它必须指向插件自己的 venv
- `working_dir` 继续表示插件执行工作目录，不等于依赖环境目录

如果后续需要存储 requirements hash 或环境状态，可以考虑新增插件环境状态表；但第一阶段优先复用现有挂载记录完成切换。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `building` | 正在创建 venv 或安装依赖 | 安装、升级、修复开始 | 成功或失败 |
| `ready` | 环境可执行 | venv 创建成功且依赖安装完成 | 损坏、升级、删除 |
| `broken` | 记录存在但环境缺失或损坏 | `python_path` 丢失、venv 目录损坏 | 修复成功或失败 |
| `failed` | 环境准备失败 | pip install 或 venv 创建失败 | 重试成功 |

## 5. 错误处理

### 5.1 错误类型

- `plugin_requirements_missing`：插件缺少 `requirements.txt`
- `plugin_env_prepare_failed`：创建 venv 或安装依赖失败
- `plugin_env_repair_failed`：启动恢复时环境修复失败
- `plugin_python_missing`：挂载记录里的 `python_path` 不存在
- `plugin_dependency_missing`：runner 执行时发现依赖仍不完整

### 5.2 错误响应格式

```json
{
  "detail": "第三方插件运行环境准备失败，请检查 requirements.txt 和安装日志。",
  "error_code": "plugin_env_prepare_failed",
  "field": null,
  "timestamp": "2026-04-07T00:00:00Z"
}
```

### 5.3 处理策略

1. 安装阶段失败：不写成伪成功安装态
2. 升级阶段失败：不切换到新版本 python_path，保留旧可用版本
3. 启动恢复失败：插件保留不可执行状态，并记录明确错误
4. runner 发现环境损坏：直接报环境错误，不 fallback 到宿主解释器

## 6. 正确性属性

### 6.1 属性 1：第三方插件解释器独立

*对于任何* 第三方插件执行请求，系统都应该满足：实际执行解释器来自插件自己的 venv，而不是宿主 `sys.executable`。

**验证需求：** 需求 1、需求 3

### 6.2 属性 2：requirements 是可执行契约

*对于任何* 正式安装或升级的第三方插件，系统都应该满足：`requirements.txt` 不只是存在校验，而是已经被安装进对应 venv。

**验证需求：** 需求 2、需求 4

## 7. 测试策略

### 7.1 单元测试

- venv 路径生成和健康检查
- requirements 变更后重装逻辑
- 环境损坏识别与修复决策

### 7.2 集成测试

- 本地安装第三方插件并创建独立 venv
- 市场安装和升级切换到新 `python_path`
- 启动恢复修复缺失 venv

### 7.3 端到端测试

- 一个带额外 Python 依赖的第三方插件在宿主未安装该依赖时仍可执行
- 宿主移除插件专属依赖后，第三方插件仍靠自己的 venv 正常运行

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.3.1、§6.1 | 安装集成测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.1、§5.3、§6.2 | 依赖安装测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§4.1、§6.1 | runner 回归测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§4.2、§5.3 | 启动恢复测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.4、§3.2 | 开发版插件测试 |
| `requirements.md` 需求 6 | `design.md` §5.1、§5.2 | 文档和错误语义检查 |

## 8. 风险与待确认项

### 8.1 风险

- Windows/Linux 下 venv 路径和可执行文件位置不同，路径处理容易写烂
- 如果升级时直接覆盖旧环境，失败回滚会很难看
- 开发版插件的 venv 位置如果选得不好，容易污染仓库或让清理策略误删源码

### 8.2 待确认项

- 开发版插件的 venv 是放在源码目录下，还是放在统一 runtime 目录下
- requirements hash 是否需要正式持久化到数据库
- 旧第三方插件首次迁移时，是懒修复还是启动时批量修复
