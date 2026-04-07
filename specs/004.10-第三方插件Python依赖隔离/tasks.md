# 任务清单 - 第三方插件Python依赖隔离（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只做一件事：把“第三方插件拥有自己的 Python 运行环境”拆成真正能做的步骤，避免最后只修一半。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

---

## 阶段 1：先把缺陷钉死，别再自欺欺人

- [x] 1.1 建立依赖隔离 Spec
  - 状态：DONE
  - 这一步到底做什么：单独新建 `004.10`，明确这不是微信插件局部修补，而是插件系统基础能力缺口。
  - 做完你能看到什么：新的需求、设计、任务文档已经建立，后面不再围着“是不是只是个小坑”打转。
  - 先依赖什么：无
  - 开始前先看：
    - `specs/004.9-插件来源模型降级与安装方式收口/`
    - `specs/000-Spec规范/Spec模板/`
  - 主要改哪里：
    - `specs/004.10-第三方插件Python依赖隔离/README.md`
    - `specs/004.10-第三方插件Python依赖隔离/requirements.md`
    - `specs/004.10-第三方插件Python依赖隔离/design.md`
    - `specs/004.10-第三方插件Python依赖隔离/tasks.md`
  - 这一步先不做什么：先不直接改安装和 runner 代码。
  - 怎么算完成：
    1. 已明确写出这次修的是插件系统，不是某个插件的特殊补丁
    2. 已明确写出安装、升级、启动恢复和执行都要切换到插件 venv
  - 怎么验证：
    - 人工检查 Spec 文件是否齐全且能读懂
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4、需求 6
  - 对应设计：`design.md` §1、§2

- [x] 1.2 记录现状缺陷证据
  - 状态：DONE
  - 这一步到底做什么：把当前系统为什么确实没有插件依赖隔离写成事实，不靠口头争论。
  - 做完你能看到什么：后续评审时能直接指出问题在哪里，而不是继续靠猜。
  - 先依赖什么：1.1
  - 开始前先看：
    - `app/modules/plugin/executors.py`
    - `app/modules/plugin/service.py`
    - `app/modules/plugin_marketplace/service.py`
  - 主要改哪里：
    - `specs/004.10-第三方插件Python依赖隔离/docs/20260407-现状缺陷确认.md`
  - 这一步先不做什么：先不设计最终目录结构。
  - 怎么算完成：
    1. 已确认 `requirements.txt` 只是存在性检查
    2. 已确认 `python_path` 当前默认写成 `sys.executable`
    3. 已确认 runner 当前只是拼 `PYTHONPATH`
  - 怎么验证：
    - 代码走查
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 6
  - 对应设计：`design.md` §2.1、§2.3、§4.1

### 阶段检查

- [x] 1.3 边界检查点
  - 状态：DONE
  - 这一步到底做什么：确认本次目标不是“继续给宿主加依赖”，而是“让第三方插件运行环境真正独立”。
  - 做完你能看到什么：后续实现不会退回到宿主依赖污染路线。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不开始写环境管理代码
  - 怎么算完成：
    1. 目标边界已经钉死
    2. 没有保留“继续复用宿主解释器”的含糊表述
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 6
  - 对应设计：`design.md` §1、§2、§6

---

## 阶段 2：把 venv 生命周期做出来

- [x] 2.1 建立插件 Python 环境管理器
  - 状态：DONE
  - 这一步到底做什么：新增统一的环境管理器，负责创建 venv、定位 python_path、安装 requirements、校验环境健康。
  - 做完你能看到什么：安装、升级和修复都能调用同一套能力，而不是每条链路各写一份脚本。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3
    - `design.md` §2.2「模块职责」
    - `design.md` §3.3「接口契约」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
  - 这一步先不做什么：先不接市场安装和启动同步
  - 怎么算完成：
    1. 能创建插件 venv
    2. 能安装 requirements
    3. 能返回可执行的 python_path
  - 怎么验证：
    - 单元测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2.2、§3.3、§4.2
  - 本次回写补充：
    1. 已新增 `app/modules/plugin/python_env.py`
    2. 已实现 venv 创建、requirements 快照、依赖安装和环境健康判断
    3. 已新增 `tests/test_plugin_python_env.py`

- [x] 2.2 定义 venv 路径和环境状态模型
  - 状态：DONE
  - 这一步到底做什么：把插件 venv 目录、python_path 规则和状态字段定下来，别让路径策略在不同入口各不相同。
  - 做完你能看到什么：后面安装、升级、修复都知道环境该放哪、坏了怎么看。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4、需求 5
    - `design.md` §3.2「数据结构」
    - `design.md` §4.1「数据关系」
  - 主要改哪里：
    - 插件 mount / marketplace instance 相关代码
    - 需要的话新增环境状态存储
  - 这一步先不做什么：先不切 runner
  - 怎么算完成：
    1. `python_path` 不再默认等于宿主解释器
    2. venv 目录规则已固定
  - 怎么验证：
    - 代码检索
    - 单元测试
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4、需求 5
  - 对应设计：`design.md` §3.2、§4.1、§4.2
  - 本次回写补充：
    1. 当前插件独立环境目录固定为 `plugin_root/.familyclaw-venv`
    2. 当前 requirements 正式快照固定为 `plugin_root/.familyclaw-requirements.txt`
    3. 当前环境健康标记使用 `venv/.requirements.sha256`

### 阶段检查

- [x] 2.3 venv 能力检查点
  - 状态：DONE
  - 这一步到底做什么：确认插件环境管理器已经能独立完成建环境和装依赖，不再是设计图。
  - 做完你能看到什么：安装链路接入前，底层能力已经站稳。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不提前切启动恢复
  - 怎么算完成：
    1. 能创建、校验、重建 venv
    2. 能处理 requirements 安装失败
  - 怎么验证：
    - 单元测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` §2.2、§3.3、§5.3
  - 本次回写补充：
    1. 环境管理器单测已验证建环境、复用环境和损坏识别
    2. 当前最小能力已经不是设计图，而是可执行代码

---

## 阶段 3：把安装、升级和启动恢复接进来

- [x] 3.1 本地安装和市场安装接入插件 venv
  - 状态：DONE
  - 这一步到底做什么：在安装/升级落盘后立刻准备插件 venv，并回写正确的 python_path。
  - 做完你能看到什么：新装的第三方插件已经不再依赖宿主解释器。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3
    - `design.md` §2.3.1「本地安装 / 市场安装」
  - 主要改哪里：
    - `app/modules/plugin/service.py`
    - `app/modules/plugin_marketplace/service.py`
  - 这一步先不做什么：先不处理开发版插件
  - 怎么算完成：
    1. 安装和升级后 `python_path` 指向插件 venv
    2. requirements 安装失败时状态明确失败
  - 怎么验证：
    - 集成测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2.3.1、§3.3.1、§5.3
  - 本次回写补充：
    1. `register_plugin_mount` 和 `install_plugin_package` 已接入环境管理器
    2. 插件市场安装和版本切换已接入环境管理器
    3. mount / marketplace instance 写回的 `python_path` 已切换到插件 venv

- [x] 3.2 启动恢复接入环境修复
  - 状态：DONE
  - 这一步到底做什么：启动同步发现 venv 丢失或损坏时，自动修复，不再继续使用旧坏路径。
  - 做完你能看到什么：重启后第三方插件环境可以自动自愈。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.3.3「启动恢复」
  - 主要改哪里：
    - `app/modules/plugin/startup_sync_service.py`
  - 这一步先不做什么：先不引入新的 UI
  - 怎么算完成：
    1. 缺失 venv 能自动重建
    2. 损坏 python_path 能自动修复或明确失败
  - 怎么验证：
    - 启动恢复测试
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §2.3.3、§4.2、§5.3
  - 本次回写补充：
    1. 启动同步的本地挂载恢复已接入环境管理器
    2. 启动同步的 marketplace instance 恢复已接入环境管理器
    3. 历史 `sys.executable` 路径现在会在恢复阶段被替换成插件 venv

### 阶段检查

- [x] 3.3 安装恢复检查点
  - 状态：DONE
  - 这一步到底做什么：确认安装、升级、启动恢复三条链路都已经走插件 venv。
  - 做完你能看到什么：不是只有一个入口修了，整个生命周期都收口了。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不提前收尾文档
  - 怎么算完成：
    1. 安装和恢复都不再把 `python_path` 写成 `sys.executable`
    2. 缺依赖时会明确失败
  - 怎么验证：
    - 集成测试
    - 代码检索
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3、§4.1、§6.1、§6.2
  - 本次回写补充：
    1. 定向回归已覆盖 `test_plugin_mounts`、`test_plugin_startup_sync`、`test_plugin_marketplace_service` 相关场景
    2. 当前安装、升级、启动恢复三条链路都已写入插件 venv `python_path`

---

## 阶段 4：切换执行链路并补开发版策略

- [x] 4.1 runner 改用插件自己的 python_path
  - 状态：DONE
  - 这一步到底做什么：执行器不再容忍第三方插件回退到宿主解释器，缺环境就直接报错。
  - 做完你能看到什么：执行链路和安装链路终于说的是同一种语言。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §2.3.4「开发版插件执行」
    - `design.md` §5.1「错误类型」
  - 主要改哪里：
    - `app/modules/plugin/executors.py`
    - 相关 runner 错误码
  - 这一步先不做什么：先不重做执行 backend 模型
  - 怎么算完成：
    1. 第三方插件 runner 只认插件 venv python_path
    2. 不再 fallback 到宿主解释器
  - 怎么验证：
    - runner 测试
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` §2.3.4、§5.1、§6.1
  - 本次回写补充：
    1. 第三方插件执行准备阶段已经会把宿主 `sys.executable` 替换成插件 venv `python_path`
    2. `config_preview` 和 `ingestor.transform` 也已切到 subprocess runner，不再直接在宿主进程 import 第三方插件
    3. 关键 runner 回归已经覆盖成功、超时、非法输出和缺依赖场景

- [x] 4.2 给开发版插件补正式依赖策略
  - 状态：DONE
  - 这一步到底做什么：让 `plugins-dev` 插件也有自己的环境准备流程，不再默认偷宿主环境。
  - 做完你能看到什么：开发版和安装版的依赖模型终于一致。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` §2.3.4「开发版插件执行」
  - 主要改哪里：
    - `app/modules/plugin/service.py`
    - `app/modules/plugin/startup_sync_service.py`
    - 开发文档
  - 这一步先不做什么：不让开发版去写安装态记录
  - 怎么算完成：
    1. `plugins-dev` 不再默认偷宿主解释器
    2. 文档写清开发版依赖准备方式
  - 怎么验证：
    - 开发版插件测试
    - 文档走查
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` §2.3.4、§3.2、§5.3
  - 本次回写补充：
    1. `plugins-dev` 构建 runner_config 时已准备插件自己的 venv
    2. 开发版插件执行不再默认偷宿主解释器
    3. 如果开发版插件环境准备失败，当前会记录问题并跳过该插件注册

---

## 阶段 5：文档、回归、验收

- [x] 5.1 更新正式文档和错误语义
  - 状态：DONE
  - 这一步到底做什么：把安装说明、插件开发文档、排障说明和错误文案同步改成新模型。
  - 做完你能看到什么：后续接手的人能看懂系统到底怎么准备插件环境。
  - 先依赖什么：4.2
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §5「错误处理」
  - 主要改哪里：
    - 正式文档
    - 错误码和提示
  - 这一步先不做什么：不再扩新功能
  - 怎么算完成：
    1. 文档已写清 venv、requirements、python_path
    2. 错误提示不再让人猜
  - 怎么验证：
    - 文档走查
    - 错误场景回归
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §5.1、§5.2
  - 本次回写补充：
    1. 正式插件开发文档已补充第三方插件 venv、requirements 和 `python_path` 规则
    2. 相关错误现在会明确落到 `plugin_env_prepare_failed` 等结构化语义

- [ ] 5.2 最终检查点
  - 状态：IN_REVIEW
  - 这一步到底做什么：确认插件依赖隔离真的成立，不再是“看起来有个 requirements.txt”。
  - 做完你能看到什么：插件系统终于不会再把第三方依赖污染成宿主依赖。
  - 先依赖什么：5.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件和相关实现
  - 这一步先不做什么：不再加新需求
  - 怎么算完成：
    1. 安装/升级会创建插件 venv
    2. requirements 会真实安装
    3. runner 使用插件自己的 python_path
    4. 不再复用宿主 `sys.executable`
  - 怎么验证：
    - 按验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
  - 本次回写补充：
    1. 安装、升级、启动恢复、runner、config_preview、ingestor.transform 关键链路都已接入插件 venv
    2. 宿主 `pyproject.toml` 里的第三方插件临时依赖已经开始回收，不再默认把插件包加回宿主依赖表
    3. 已额外回归开发版覆盖、安装态恢复、市场安装/升级、runner、config_preview 和 memory ingest 关键用例
    4. 还需要再做一轮更大范围的全量插件回归，确认没有遗漏的第三方执行入口
