# 需求文档 - 第三方插件Python依赖隔离

状态：Draft

## 简介

当前第三方插件虽然有独立源码目录、安装目录和挂载记录，但它们没有独立 Python 依赖环境。

现实表现非常直接：

- 插件市场要求插件仓库带 `requirements.txt`
- 安装流程只检查它是否存在
- 执行流程仍然使用宿主 `sys.executable`
- 插件 import 是否成功，取决于宿主环境恰好装了什么

这会把第三方插件依赖污染成宿主依赖，也会让“插件能否运行”变成碰运气。

这次要补的是插件系统本身的运行能力：第三方插件要有自己的 Python 解释器和依赖环境，安装、升级、恢复和执行都按这个模型走。

## 术语表

- **System**：FamilyClaw 宿主与第三方插件运行系统
- **插件运行环境**：某个第三方插件对应的独立 Python venv 及其已安装依赖
- **安装态插件**：通过 `local` 或 `marketplace` 安装落盘的第三方插件
- **开发版插件**：位于 `apps/api-server/plugins-dev/`、参与加载的第三方插件源码
- **runner python_path**：插件执行时实际使用的 Python 可执行文件路径

## 范围说明

### In Scope

- 为第三方插件创建独立 Python venv
- 安装和升级时安装插件 `requirements.txt`
- 启动恢复时修复缺失或损坏的插件 venv
- 插件 runner 改用插件自己的 `python_path`
- 文档和错误语义同步更新

### Out of Scope

- builtin 插件依赖隔离
- 非 Python 插件运行时隔离
- 重做插件市场 UI
- 引入新的包管理工具链

## 需求

### 需求 1：安装和升级必须创建插件自己的 venv

**用户故事：** 作为平台维护者，我希望第三方插件在安装和升级时自动创建自己的 Python venv，以便插件依赖不再污染宿主环境。

#### 验收标准

1. WHEN 本地安装一个第三方插件 THEN System SHALL 为该插件创建独立 venv。
2. WHEN 市场安装或升级一个第三方插件 THEN System SHALL 为目标版本创建或刷新独立 venv。
3. WHEN 插件版本切换完成 THEN System SHALL 把挂载记录里的 `python_path` 指向该插件自己的 venv，而不是宿主 `sys.executable`。

### 需求 2：插件 requirements.txt 必须真的被安装

**用户故事：** 作为插件开发者，我希望插件声明的 `requirements.txt` 被真实安装，而不是只被检查文件存在，以便我的插件依赖是可执行契约，不是摆设。

#### 验收标准

1. WHEN 安装或升级第三方插件 THEN System SHALL 在插件 venv 中安装 `requirements.txt` 里的依赖。
2. WHEN 依赖安装失败 THEN System SHALL 返回明确错误，并把安装状态标记为失败，而不是留下一个半成品挂载。
3. WHEN `requirements.txt` 为空或只有宿主已具备的包 THEN System SHALL 仍然完成 venv 初始化，不因“无需额外依赖”跳过隔离流程。

### 需求 3：runner 必须使用插件自己的 python_path

**用户故事：** 作为系统维护者，我希望第三方插件执行时统一使用插件自己的 Python 解释器，以便运行结果只受插件自身环境影响。

#### 验收标准

1. WHEN 第三方插件通过 `subprocess_runner` 执行 THEN System SHALL 使用插件 venv 中的 `python_path`。
2. WHEN 插件缺少有效 `python_path` THEN System SHALL 明确报“运行环境未准备好”，而不是回退到宿主解释器。
3. WHEN 代码评审检查插件 mount 和 marketplace instance THEN System SHALL 不再把 `python_path` 默认写成 `sys.executable`。

### 需求 4：启动恢复必须能修复插件运行环境

**用户故事：** 作为运维人员，我希望系统启动时能发现并修复第三方插件丢失或损坏的 venv，以便重启后插件不会因为环境丢失直接报废。

#### 验收标准

1. WHEN 启动同步发现第三方插件 mount 存在但 venv 缺失 THEN System SHALL 重建该插件 venv 并重新安装依赖。
2. WHEN venv 中的 python 可执行文件不存在 THEN System SHALL 视为环境损坏并触发修复，而不是继续保留旧路径。
3. WHEN 自动修复失败 THEN System SHALL 给出结构化错误并保留插件禁用/不可执行状态，不能假装恢复成功。

### 需求 5：开发版插件也必须有明确依赖策略

**用户故事：** 作为插件开发者，我希望 `plugins-dev` 下的开发版插件也有可预期的依赖策略，以便开发版和安装版不会在宿主环境上互相踩。

#### 验收标准

1. WHEN 系统加载 `plugins-dev` 下的第三方插件 THEN System SHALL 明确采用一套正式依赖策略，而不是默认偷用宿主环境。
2. WHEN 开发版插件首次需要执行 THEN System SHALL 能创建或提示创建它自己的 venv，而不是 silently fallback 到宿主解释器。
3. WHEN 文档描述开发版插件行为 THEN System SHALL 写清楚开发版插件依赖如何准备、如何修复、如何排障。

### 需求 6：文档和错误语义必须说人话

**用户故事：** 作为后续接手的人，我希望从文档和错误提示里一眼看懂插件环境是不是没准备好，以便排障时不靠猜。

#### 验收标准

1. WHEN 第三方插件缺少运行环境 THEN System SHALL 返回明确错误码和可读说明，而不是只给 `ModuleNotFoundError`。
2. WHEN 官方文档介绍第三方插件安装和执行 THEN System SHALL 明确写出插件 venv 和 `requirements.txt` 的行为。
3. WHEN 后续有人开发第三方 Python 插件 THEN System SHALL 能从文档里看到“宿主不会再替插件背依赖”这一事实。

## 非功能需求

### 非功能需求 1：可靠性

1. WHEN 插件安装中断或依赖安装失败 THEN System SHALL 保持状态可恢复，不留下伪成功挂载。
2. WHEN 插件环境修复完成 THEN System SHALL 能继续执行，不要求人工直接改数据库字段。

### 非功能需求 2：可维护性

1. WHEN 后续新增第三方 Python 插件 THEN System SHALL 复用同一套 venv 管理逻辑，而不是每个安装入口各写一套。
2. WHEN 排障依赖问题 THEN System SHALL 能直接看出插件的 venv 目录、python_path 和依赖安装结果。

### 非功能需求 3：兼容性

1. WHEN 现有第三方插件升级到新系统 THEN System SHALL 有明确迁移路径，不要求一次性重装所有插件才能启动。
2. WHEN 历史 mount 记录中的 `python_path` 仍指向宿主解释器 THEN System SHALL 能识别并迁移，而不是长期兼容这个坏状态。

## 成功定义

- 第三方插件安装和升级后都拥有自己的 venv
- 插件 `requirements.txt` 被真实安装，而不是只检查文件存在
- runner 执行第三方插件时不再复用宿主 `sys.executable`
- 启动恢复能发现并修复插件缺失或损坏的运行环境
- 文档和错误提示已经把新模型讲清楚
