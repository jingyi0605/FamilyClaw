# 设计文档 - 插件 ZIP 手动安装、覆盖升级与安装后立即生效

状态：In Progress

## 1. 概述

### 1.1 目标

- 给插件管理页补一个正式的 ZIP 手动安装入口
- 让 ZIP 手动安装支持同插件 ID 的覆盖升级
- 明确“安装后立即生效”的真实语义
- 让 ZIP 安装和市场安装在运行时生效边界上统一
- 避免把这次需求做成假的 Python 热重载

### 1.4 当前实现回写

- 后端 ZIP 安装接口、版本目录托管、覆盖升级和挂载切换已经落地
- 后端已经把运行时安装插件固定收口到 `subprocess_runner`
- 插件市场安装、启用、升级已经按“无需重启后端服务，后续查询和下一次执行识别当前挂载”的语义运行
- `user-app` 里的 ZIP 上传面板和覆盖确认还没接入，所以前端体验仍未收口

### 1.2 覆盖需求

- `requirements.md` 需求 1：插件管理页必须支持本地 ZIP 上传安装
- `requirements.md` 需求 2：后端必须在安装前校验 ZIP 包结构和 manifest
- `requirements.md` 需求 3：系统必须支持同插件 ID 的覆盖升级安装
- `requirements.md` 需求 4：安装成功后必须立即进入新挂载链路，无需重启后端
- `requirements.md` 需求 5：运行时可安装插件必须遵守统一的隔离执行边界
- `requirements.md` 需求 6：已在运行中的旧任务和待执行任务必须有清楚边界
- `requirements.md` 需求 7：市场插件安装、启用和升级也必须明确为无需重启后端
- `requirements.md` 需求 8：错误、回滚和文档口径必须一致

### 1.3 技术约束

- 后端沿用 FastAPI + SQLAlchemy + 现有 `app.modules.plugin`、`app.modules.plugin_marketplace`
- 前端只改 `apps/user-app`
- 必须遵守 `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
- 必须遵守 `docs/开发设计规范/20260317-插件挂载与运行隔离开发规范.md`
- 不新增“需要手工重启服务”的安装后步骤
- 不承诺 `in_process` 插件的 Python 模块原位热替换

## 2. 架构

### 2.1 系统结构

这次最重要的不是上传文件，而是统一运行时安装插件的边界。

整体拆成五层：

1. **前端上传入口层**
   - 目标是插件管理页提供 ZIP 选择、覆盖安装确认、结果展示
   - 当前真实状态是：后端上传接口已完成，`user-app` 页面入口待补

2. **ZIP 安装流水线**
   - 接收文件
   - 解压到临时目录
   - 校验 manifest 和必要文件
   - 计算安装目标
   - 托管到版本目录

3. **挂载切换层**
   - 首次安装时创建 `PluginMount`
   - 覆盖升级时切换 `PluginMount.plugin_root` 和 `manifest_path`
   - 保留旧稳定状态，失败时回滚

4. **运行时生效层**
   - 插件列表、详情、启停、执行都继续通过家庭插件快照读取当前挂载
   - 运行时安装插件统一按隔离执行语义处理

5. **任务边界层**
   - 已运行任务继续旧版本
   - 待执行任务在真正执行前重新解析快照

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `PluginPackageUploadEndpoint` | 接收 ZIP 上传请求 | ZIP 文件、覆盖标记、家庭 ID | 安装结果 |
| `PluginPackageInstallService` | 执行 ZIP 安装流水线 | 临时解压目录、manifest、覆盖标记 | 挂载切换结果 |
| `PluginPackageValidator` | 校验 ZIP 结构与 manifest | 解压目录 | 校验结果 |
| `PluginMountSwitchService` | 创建或切换挂载 | 新版本目录、当前挂载 | 新挂载或回滚结果 |
| `PluginRuntimePolicy` | 统一运行时安装插件的执行边界 | 插件来源、执行请求 | 执行后端决策 |
| `PluginJobs / Worker` | 在任务执行前重新读当前快照 | 任务请求 | 真正执行结果 |

### 2.3 关键流程

#### 2.3.1 ZIP 首次安装流程

1. 当前先由管理员通过 `POST /api/v1/ai-config/{household_id}/plugin-packages` 提交 ZIP 包；插件管理页入口待补。
2. 前端接入后，页面会把 ZIP 包和安装参数提交给后端。
3. 后端将 ZIP 解压到临时目录。
4. 校验 `manifest.json`、入口、必要文件和路径安全。
5. 计算托管目标目录：
   - `data/plugins/third_party/manual/<household_id>/<plugin_id>/<version>--<timestamp>--<id>/`
6. 复制插件内容到托管目录。
7. 创建或补齐 `PluginMount`，执行后端固定为 `subprocess_runner`，首次安装默认 `enabled=false`。
8. 返回安装结果。
9. 前端刷新插件列表和详情。

补充说明：
- 手动 ZIP 安装不会覆盖写回旧版本目录，而是每次生成新的 release 目录名，避免覆盖过程把当前可用版本一并砸坏。
- 启动同步会兼容旧的 `<version>/` 目录和新的 release 目录布局，并优先选取最近一次成功安装的 release 作为当前挂载。

#### 2.3.2 ZIP 覆盖升级流程

1. 管理员再次上传同一 `plugin_id` 的新版本 ZIP。
2. 当前接口必须显式传 `overwrite=true`；页面确认交互待前端补上。
3. 后端完成临时解压和校验。
4. 新版本落到新的版本目录，而不是原地覆盖旧目录。
5. 记录当前挂载快照，切换 `PluginMount.plugin_root / manifest_path / working_dir` 到新版本目录。
6. 若切换后后续校验失败，则回滚到旧挂载。
7. 切换成功后返回“覆盖升级完成”。

#### 2.3.3 安装后立即生效流程

1. 安装成功后，前端重新请求插件列表和插件详情。
2. 后端继续通过 `list_registered_plugins_for_household` 从当前 `PluginMount` 构建快照。
3. 下一次启用、执行、任务出队时都会读取新挂载。
4. 整个过程不依赖服务重启。

#### 2.3.4 任务与执行边界流程

1. 如果某个插件任务已经开始执行，则继续跑旧版本代码直到收口。
2. 如果某个任务只是排队未开始，则在真正执行前再次调用 `require_available_household_plugin(...)` 和当前挂载解析。
3. 因为运行时安装插件统一走隔离执行，所以新任务会直接读到新版本目录。

#### 2.3.5 市场安装一致性流程

1. 市场安装、启用、升级完成后，也按当前挂载和实例状态重新进入后续链路。
2. 市场插件不再用“重启后端后才算生效”这种暧昧语义。
3. 文档和页面统一表达为：
   - 安装成功后已进入已安装状态
   - 默认仍未启用
   - 启用后后续执行立即生效
   - 已运行任务不会被强行热切换

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7、8

- `PluginPackageInstallService`：统一处理 ZIP 上传安装和覆盖升级
- `PluginPackageValidator`：校验 ZIP 包与 manifest
- `PluginRuntimeInstallResultRead`：返回给前端的安装结果
- `PluginRuntimePolicy`：统一运行时安装插件的执行边界
- 插件管理页上传面板：上传 ZIP、确认覆盖、展示结果

### 3.2 数据结构

覆盖需求：2、3、4、5、6、7

#### 3.2.1 `PluginPackageInstallRequest`（当前实现）

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `overwrite` | boolean | 否 | 是否允许覆盖升级 | 默认 `false` |

说明：

- `household_id` 当前放在路径里，不在请求体里重复传。
- 当前实现没有 `enable_after_install` 字段；首次安装固定不自动启用。

#### 3.2.2 `PluginPackageInstallRead`（当前实现）

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `household_id` | string | 是 | 家庭 ID | 非空 |
| `plugin_id` | string | 是 | 插件 ID | 非空 |
| `plugin_name` | string | 是 | 插件名称 | 非空 |
| `version` | string | 是 | 安装版本 | 非空 |
| `previous_version` | string | 否 | 覆盖前版本 | 首次安装为空 |
| `install_action` | string | 是 | `installed` / `upgraded` / `reinstalled` | 稳定枚举 |
| `overwritten` | boolean | 是 | 这次是否覆盖了现有第三方手动安装 | 布尔值 |
| `enabled` | boolean | 是 | 当前挂载是否已启用 | 首次安装默认 `false` |
| `source_type` | string | 是 | 当前固定为 `third_party` | 稳定值 |
| `execution_backend` | string | 是 | 当前固定为 `subprocess_runner` | 稳定值 |
| `plugin_root` | string | 是 | 当前生效插件目录 | 非空 |
| `manifest_path` | string | 是 | 当前生效 manifest 路径 | 非空 |
| `message` | string | 是 | 返回给调用方的人话提示 | 非空 |

#### 3.2.3 托管目录规则

| 目录 | 用途 | 说明 |
| --- | --- | --- |
| `data/plugins/third_party/manual/<household_id>/<plugin_id>/<version>--<timestamp>--<id>/` | 手工 ZIP 安装 release 目录 | 每次安装生成独立 release，便于覆盖升级时安全切换 |
| `PluginMount.plugin_root` | 当前生效目录 | 永远指向当前版本目录 |
| `PluginMount.manifest_path` | 当前 manifest | 永远指向当前版本目录里的 manifest |

### 3.3 接口契约

覆盖需求：1、2、3、4、7、8

#### 3.3.1 上传 ZIP 安装插件

- 类型：HTTP
- 路径或标识：`POST /api/v1/ai-config/{household_id}/plugin-packages`
- 请求格式：`multipart/form-data`
- 输入：
  - `file`: ZIP 文件
  - `overwrite`: `true/false`
- 输出：`PluginPackageInstallRead`
- 校验：
  - 文件必须存在
  - 文件必须是 ZIP
  - ZIP 结构必须合法
  - 若存在同 `plugin_id` 挂载且 `overwrite=false`，拒绝安装
- 错误：
  - `plugin_package_missing`
  - `plugin_package_invalid`
  - `plugin_package_conflict`
  - `plugin_id_conflict`
  - `plugin_source_mismatch`
  - `plugin_runtime_install_failed`

#### 3.3.2 查询插件列表

- 类型：HTTP
- 路径或标识：沿用 `GET /api/v1/ai-config/{household_id}/plugins`
- 行为变化：
  - 安装或覆盖升级成功后，刷新此接口即可看到新挂载
  - 返回结果要能让前端知道当前版本已立即生效、无需重启

#### 3.3.3 市场插件启用与升级语义补充

- 类型：HTTP
- 路径或标识：
  - `POST /api/v1/plugin-marketplace/instances/{instance_id}/enable`
  - `POST /api/v1/plugin-marketplace/instances/{instance_id}/version-operations`
- 行为补充：
  - 返回结果和文档必须明确 `restart_required=false`
  - 前端成功提示文案不得再暗示“重启后生效”

## 4. 数据与状态模型

### 4.1 数据关系

这次不要再发明新的“运行时安装状态表”。

核心真相仍然只有这些：

1. ZIP 包内容决定本次待安装版本的 manifest 真相。
2. `PluginMount` 决定当前家庭后续真正生效的是哪个目录。
3. 插件列表和执行链路继续从当前挂载构建快照。
4. 市场插件额外有 `PluginMarketplaceInstance`，但其“立即生效”边界和手工 ZIP 应一致。

### 4.2 状态流转

#### 4.2.1 ZIP 安装操作状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `uploading` | 前端正在上传 ZIP | 用户提交 | 上传完成或失败 |
| `extracting` | 后端正在解压 | 收到文件 | 校验或失败 |
| `validating` | 正在校验 manifest 和包结构 | 解压成功 | 可安装或失败 |
| `switching_mount` | 正在创建或切换挂载 | 校验通过 | 成功或回滚 |
| `completed` | 安装完成 | 切换成功 | 再次操作 |
| `failed` | 安装失败 | 任一步骤失败 | 用户重试 |

#### 4.2.2 生效边界状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `running_old_code` | 旧任务仍在跑旧版本 | 升级时已有执行中的任务 | 任务完成 |
| `queued_use_new_mount` | 未开始的任务会用新挂载 | 安装或升级成功 | 任务出队并执行 |
| `ready_for_next_execution` | 后续直接基于新挂载 | 安装或升级成功 | 再次切换版本 |

### 4.3 关键不变量

1. ZIP 覆盖升级必须优先写入新版本目录，再切换挂载，不能先破坏旧挂载。
2. 安装成功不等于自动启用。
3. 运行时可安装插件的“立即生效”只保证后续查询和下一次执行，不保证主进程模块热替换。
4. 已运行任务不强行热切换代码。
5. 待执行任务在真正执行前必须重新读当前挂载。

## 5. 错误处理

### 5.1 错误类型

- `plugin_package_missing`：未上传文件
- `plugin_package_invalid`：不是合法 ZIP 或解压结构非法
- `plugin_package_conflict`：当前操作其实是覆盖升级，但调用方未显式传 `overwrite=true`
- `plugin_id_conflict`：上传包的 `plugin_id` 和内置插件冲突
- `plugin_source_mismatch`：当前插件来源和这次 ZIP 覆盖来源不兼容
- `plugin_mount_switch_failed`：新目录已准备，但挂载切换失败
- `plugin_runtime_install_failed`：运行时安装总入口失败
- `plugin_runtime_reload_boundary`：用户或前端试图把本次能力解释成模块热替换

### 5.2 错误响应格式

```json
{
  "detail": "插件 demo-plugin 已经存在，覆盖升级请勾选 overwrite。",
  "error_code": "plugin_package_conflict",
  "field": "overwrite",
  "timestamp": "2026-03-19T00:00:00Z"
}
```

### 5.3 处理策略

1. 上传缺文件或文件格式不对：直接拒绝，不进入安装流水线。
2. ZIP 校验失败：清理临时目录，不写挂载。
3. 覆盖升级切换失败：回滚到旧挂载，保持旧版本可用。
4. 页面文案误导风险：统一改成“无需重启，后续执行生效”，不用“热重载完成”这种假话。

## 6. 正确性属性

### 6.1 属性 1：新挂载切换原子化

*对于任何* ZIP 覆盖升级请求，系统都应该满足：要么新版本目录准备完成并切换成功，要么继续保留旧挂载，不出现半切换状态。

**验证需求：** 需求 3、需求 8

### 6.2 属性 2：运行时生效不依赖重启

*对于任何* ZIP 安装、市场安装、启用或升级操作，只要接口返回成功，系统都应该满足：后续查询和下一次执行可以直接消费新挂载或新状态，而不是等待服务重启。

**验证需求：** 需求 4、需求 7

### 6.3 属性 3：旧任务不被强行热切换

*对于任何* 已经开始执行的插件任务，系统都应该满足：该次运行按旧版本收口，不把代码执行过程硬切到新版本。

**验证需求：** 需求 6

## 7. 测试策略

### 7.1 单元测试

- ZIP 包结构校验
- manifest 校验
- 覆盖升级前置判断
- 生效边界说明生成

### 7.2 集成测试

- 首次 ZIP 安装成功
- ZIP 覆盖升级成功
- 未确认覆盖时被阻断
- 切换失败时旧挂载回滚
- 市场插件安装后无需重启即可查询到
- 市场插件启用后无需重启即可进入后续执行链路

### 7.3 端到端测试

- 插件管理页上传 ZIP 安装
- 上传同插件 ZIP 时弹出覆盖确认
- 安装完成后列表刷新立即看到新版本
- 页面文案明确“已安装未启用”和“后续执行将使用新版本”

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.3.1 | 端到端测试、前端走查 |
| `requirements.md` 需求 2 | `design.md` §2.3.1、§5.1 | 单元测试、集成测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.2、§4.3 | 集成测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§6.2 | 集成测试、端到端测试 |
| `requirements.md` 需求 5 | `design.md` §2.1、§4.3、§6.2 | 架构走查、集成测试 |
| `requirements.md` 需求 6 | `design.md` §2.3.4、§6.3 | 集成测试 |
| `requirements.md` 需求 7 | `design.md` §2.3.5、§3.3.3 | 集成测试、前端走查 |
| `requirements.md` 需求 8 | `design.md` §5、§6.1 | 集成测试、文档走查 |

## 8. 风险与待确认项

### 8.1 风险

- 如果继续允许运行时安装插件走 `in_process`，那“立即生效”一定会变成含糊话术。
- 如果覆盖升级仍然原地覆写目录，失败时很容易把旧版本一起搞坏。
- 如果前端把“立即生效”文案写成“插件已热重载”，后面一定有人拿这个去要求模块级热替换。

### 8.2 待确认项

- 是否为 ZIP 手动安装增加单独安装记录表，还是继续只依赖 `PluginMount` 表达当前版本。
- 是否在插件管理页展示“当前运行中的旧任务仍按旧版本收口”的说明文案。
- 是否把所有运行时安装插件统一强制成 `subprocess_runner`，并同时修正现有市场安装链路对 `official` 来源的执行后端漂移问题。
