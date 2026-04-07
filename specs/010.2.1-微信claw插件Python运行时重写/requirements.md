# 需求文档 - 微信claw插件Python运行时重写

状态：Draft

## 简介

当前微信 claw 插件虽然已经插件化，但它的后端主链路仍然依赖 Node 子层。结果很现实：

- 宿主镜像要么额外安装 Node.js
- 要么微信插件一启用就因为运行时缺失直接报错
- 插件手册也不得不解释两套运行时怎么拼在一起

这不符合项目现在的插件边界要求。

这次要做的是把微信插件的后端逻辑完整迁回 Python，让宿主和插件后端统一只依赖一套运行时，同时保持现有宿主接口、账号配置方式和主要用户流程不被破坏。

## 术语表

- **System**：FamilyClaw 宿主和微信 claw 第三方插件组成的整体系统
- **Python transport**：本次要落地的新实现，负责直接用 Python 完成扫码登录、状态轮询、消息拉取、消息发送和媒体处理
- **旧 Node 子层**：当前 `plugin/bridge.py + vendor/weixin_transport/` 这套跨语言调用链
- **运行时状态**：插件私有目录里的登录态、轮询游标、`context_token`、媒体缓存、日志和临时二维码文件
- **插件手册**：微信插件 README、相关开发文档和后续插件开发规则

## 范围说明

### In Scope

- 用 Python 替换微信插件现有 Node bridge 和 Node transport
- 保持宿主调用的 `config_preview`、`action`、`channel` 契约不变
- 保持现有运行时状态模型继续可用，必要时做兼容迁移
- 删除运行时对 Node.js 的依赖，并同步更新插件手册
- 在文档层明确以后插件后端逻辑必须使用 Python 实现

### Out of Scope

- 扩展微信插件的新平台能力，比如群聊、联系人管理、朋友圈
- 修改宿主通用插件协议来迁就微信私有细节
- 在这一轮把所有第三方插件都一并改造成 Python-only

## 需求

### 需求 1：微信插件后端必须只依赖 Python 运行时

**用户故事：** 作为系统维护者，我希望微信插件后端只依赖 Python，以便部署环境不需要为了一个插件额外安装 Node.js。

#### 验收标准

1. WHEN 宿主执行微信插件的 `config_preview`、`action` 或 `channel` 入口 THEN System SHALL 不再启动任何 Node.js 进程。
2. WHEN Docker 运行镜像只包含 Python 运行时 THEN System SHALL 仍然可以完成微信插件的主要链路。
3. WHEN 代码评审检查插件目录 THEN System SHALL 不再保留 Node bridge 作为正式运行依赖。

### 需求 2：宿主接口和主要用户流程不能被破坏

**用户故事：** 作为家庭管理员，我希望插件重写后现有的扫码登录、状态刷新和账号管理方式还能继续用，以便升级后不用重学一遍。

#### 验收标准

1. WHEN 管理员点击“生成扫码二维码” THEN System SHALL 继续通过现有 `config_preview` 返回二维码预览和运行时状态。
2. WHEN 管理员点击“刷新登录状态” THEN System SHALL 继续返回统一的登录状态摘要，而不是新的私有字段。
3. WHEN 宿主已经按旧契约调用 `start_login`、`get_login_status`、`poll`、`send` THEN System SHALL 不要求宿主改接口才能继续工作。

### 需求 3：Python transport 必须补齐现有正式能力

**用户故事：** 作为家庭成员，我希望微信插件重写后还能像现在一样收消息、发消息和维持回复上下文，以便迁移不是功能倒退。

#### 验收标准

1. WHEN 插件执行 `start_login` THEN System SHALL 能生成二维码内容并保存对应登录会话。
2. WHEN 插件执行 `poll` THEN System SHALL 能继续拉取微信消息、做标准化并维护轮询游标。
3. WHEN 插件执行 `send` THEN System SHALL 能继续发送文本和当前第一版已支持的基础媒体，并正确使用或恢复 `context_token`。

### 需求 4：运行时状态必须兼容迁移，不能让已有账号全量报废

**用户故事：** 作为系统维护者，我希望已有微信账号的插件运行状态尽量能被新实现继续识别，以便升级时不把所有账号都打回未登录。

#### 验收标准

1. WHEN 插件目录里已经存在旧运行时 SQLite 和二维码缓存 THEN System SHALL 明确定义哪些字段直接复用、哪些字段需要迁移、哪些字段允许丢弃。
2. WHEN 旧状态无法被安全复用 THEN System SHALL 给出明确错误或重登提示，而不是静默损坏状态。
3. WHEN 迁移完成 THEN System SHALL 不再依赖 Node 专属状态结构才能运行。

### 需求 5：插件手册和开发规则必须同步更新

**用户故事：** 作为后续插件开发者，我希望文档明确写清插件后端的运行时边界，以便以后不会再随手往后端塞第二套语言运行时。

#### 验收标准

1. WHEN 本次重写合入 THEN System SHALL 同步更新微信插件 README，删除 Node 运行时要求。
2. WHEN 更新插件开发相关文档 THEN System SHALL 明确写出“插件后端逻辑和代码必须使用 Python 完成”。
3. WHEN 后续有人参考文档开发新插件 THEN System SHALL 不再把 Node bridge 当成官方推荐路线。

## 非功能需求

### 非功能需求 1：性能

1. WHEN 执行扫码登录和状态刷新 THEN System SHALL 保持与当前实现同量级的响应时间，不因为重写出现明显卡顿。
2. WHEN 执行轮询和发消息 THEN System SHALL 不因为 Python 重写导致宿主线程被长时间阻塞。

### 非功能需求 2：可靠性

1. WHEN 微信上游请求失败、超时或返回脏数据 THEN System SHALL 继续返回结构化错误，并保留排障日志。
2. WHEN 插件进程重启后继续运行 THEN System SHALL 能从插件私有状态中恢复必要的登录态、游标和 `context_token`。

### 非功能需求 3：可维护性

1. WHEN 后续继续扩展微信插件能力 THEN System SHALL 在 Python 代码内完成，不再新增跨语言桥接层。
2. WHEN 维护者排障或升级插件 THEN System SHALL 只需要理解 Python 代码、插件私有状态和宿主标准契约。

## 成功定义

- 微信插件在纯 Python 运行镜像中可以完成扫码登录、状态刷新、消息轮询和文本发送主链路
- 宿主不再需要为了微信插件安装 Node.js
- 微信插件 README 和插件开发规则已经明确禁止插件后端引入第二套运行时
- 旧 Node 子层正式退出运行链路，而不是继续挂着“暂时兼容”
