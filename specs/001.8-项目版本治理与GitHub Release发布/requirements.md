# 需求文档 - 项目版本治理与 GitHub Release 发布

状态：Draft

## 简介

FamilyClaw 现在缺的不是“再多写几个版本号”，而是缺一个所有发布动作都必须服从的唯一事实源。当前版本信息散落在 Python 配置、多个 `package.json`、多个 `pyproject.toml` 和运行时代码里，已经足够让后续 Docker 发布、插件兼容性判断、用户界面展示和问题排查互相打架。

这份 Spec 要把版本治理收口成一条清楚的链路：

- 仓库里谁说了算
- GitHub Release 怎么生成
- Docker 镜像怎么标记
- 运行中的应用怎么暴露自己的版本
- 数据库 schema 版本和应用版本怎么建立关系

这次方案明确以 GitHub Release 为中心，不额外部署版本服务。

## 术语表

- **System**：FamilyClaw 项目整体，包括 `api-server`、`open-xiaoai-gateway`、`user-app`、Docker 镜像和发布资产
- **应用版本**：面向项目发布的宿主版本，采用 SemVer，例如 `0.3.0`
- **发布事实源**：发布后可以拿来追责和核对的唯一来源，本 Spec 中指 Git tag、GitHub Release 和对应 Release 资产
- **Schema 版本**：数据库表结构版本，继续使用 Alembic revision / head 表示
- **Release 清单**：每个应用版本附带的一份结构化元数据，记录应用版本、Git SHA、镜像、Schema head 和升级边界

## 范围说明

### In Scope

- 定义应用版本的唯一事实源和版本格式
- 定义 Git tag、GitHub Release、GHCR 镜像标签之间的关系
- 定义版本同步机制，避免多个子项目手工各改各的
- 定义运行时版本暴露方式
- 定义应用版本与数据库 schema 版本的兼容性记录方式
- 定义最小可用的发布校验和发布流水线边界

### Out of Scope

- 在线自动升级服务
- 自建发布后台
- 强制联网的版本检查
- 完整的软件供应链签名体系
- 数据库差量迁移平台化

## 需求

### 需求 1：统一应用版本事实源

**用户故事：** 作为维护者，我希望整个仓库只有一个应用版本事实源，这样发版时不会漏改、错改或把几个组件改成不同版本。

#### 验收标准

1. WHEN 维护者准备发布新版本 THEN System SHALL 只要求修改一个明确的版本源文件，而不是手工修改多个子项目版本号。
2. WHEN 版本同步脚本执行 THEN System SHALL 把根版本同步到需要对外暴露版本的 Python 和 Node 配置文件。
3. WHEN 任一子项目版本与根版本不一致 THEN System SHALL 在本地脚本或 CI 中明确报错并阻断发布。

### 需求 2：GitHub Release 成为发布事实源

**用户故事：** 作为发布负责人，我希望 Git tag、GitHub Release 和 Docker 镜像标签能互相对上，这样出了问题能立刻知道某个镜像到底对应哪次发布。

#### 验收标准

1. WHEN 创建形如 `vX.Y.Z` 或 `vX.Y.Z-rc.N` 的 Git tag THEN System SHALL 只为该 tag 生成对应的 GitHub Release 和镜像标签。
2. WHEN GitHub Release 创建成功 THEN System SHALL 产出结构化 Release 清单，而不是只留一段自由文本说明。
3. WHEN 维护者查看任意一个 Release THEN System SHALL 能从 Release 清单中看到应用版本、Git SHA、镜像地址和数据库 schema 目标。

### 需求 3：运行中的应用必须能自报家门

**用户故事：** 作为排查问题的人，我希望正在运行的 FamilyClaw 能明确告诉我自己是什么版本、来自哪个提交、对应哪个 Release，这样我不用猜。

#### 验收标准

1. WHEN 调用系统版本接口或查看设置页版本信息 THEN System SHALL 返回当前应用版本、Git SHA、构建时间、Release 链接和 schema 目标信息。
2. WHEN 镜像是正式 Release 构建出来的 THEN System SHALL 返回与 GitHub Release 一致的版本元数据。
3. WHEN 版本元数据缺失或构建方式不完整 THEN System SHALL 明确标记为未知或开发构建，而不是伪造稳定版本信息。

### 需求 4：应用版本与数据库 schema 关系必须可追踪

**用户故事：** 作为维护者，我希望升级应用时能知道它期望的数据库 schema 是什么、能从哪些旧库安全升级，这样升级不是碰运气。

#### 验收标准

1. WHEN 生成某个应用 Release 的清单 THEN System SHALL 记录该 Release 对应的 Alembic head 列表，而不是只写一个模糊的“数据库版本号”。
2. WHEN 两个应用版本没有 schema 变化 THEN System SHALL 允许它们指向同一个 Alembic head，而不强迫制造新的数据库版本编号。
3. WHEN 某个 Release 需要人工迁移或不支持从过旧 schema 直接升级 THEN System SHALL 在 Release 清单中显式记录升级边界、人工步骤文档或阻断原因。

### 需求 5：不额外部署服务器也能完成发布治理

**用户故事：** 作为项目负责人，我希望版本治理依赖 GitHub 和仓库本身就能完成，不需要额外维护一个发布服务。

#### 验收标准

1. WHEN 完成一次正式发布 THEN System SHALL 只依赖仓库、GitHub Actions、GitHub Release 和 GHCR，不需要额外部署自有服务。
2. WHEN 家庭 NAS 用户离线运行容器 THEN System SHALL 仍然能读取镜像内嵌的版本元数据，不依赖运行时访问 GitHub。
3. WHEN 未来需要可选的“检查更新”能力 THEN System SHALL 可以读取 GitHub Release API，但运行和升级流程本身 SHALL 不依赖该在线能力才能成立。

### 需求 6：版本规则必须和现有插件宿主兼容性机制兼容

**用户故事：** 作为插件维护者，我希望宿主版本规则保持稳定，这样 `min_app_version` 的判断逻辑不会因为宿主版本机制再次推倒重来。

#### 验收标准

1. WHEN 宿主应用发布新版本 THEN System SHALL 继续使用可比较的 SemVer 版本文本供插件兼容性逻辑消费。
2. WHEN 插件市场校验 `min_app_version` THEN System SHALL 能直接使用宿主应用版本，不需要额外引入另一套数据库版本号参与插件兼容比较。
3. WHEN 宿主版本是预发布版本 THEN System SHALL 明确定义是否允许插件比较规则继续解析该版本文本。

## 非功能需求

### 非功能需求 1：可维护性

1. WHEN 新增新的对外组件或构建产物 THEN System SHALL 能通过扩展版本同步脚本和 Release 清单字段纳管，而不是再手工复制一套版本流程。
2. WHEN 维护者排查版本问题 THEN System SHALL 让“根版本源、同步脚本、Release 清单、运行时接口”这几处关系足够直白，不需要反推隐藏逻辑。

### 非功能需求 2：可靠性

1. WHEN 发布流程中任一关键步骤失败 THEN System SHALL 阻断 Release 创建或镜像发布，避免留下半成品版本。
2. WHEN 版本同步、Tag 校验或 Release 清单生成结果不一致 THEN System SHALL 返回明确错误，而不是悄悄放过。

### 非功能需求 3：可审计性

1. WHEN 维护者回看历史版本 THEN System SHALL 能通过 GitHub Release 资产追溯到版本、提交、镜像和 schema 目标。
2. WHEN 用户上报某个运行实例的问题 THEN System SHALL 支持通过运行时版本信息快速定位对应 Release 和源码提交。

## 成功定义

- 仓库里应用版本事实源收口到一个位置，发版不再需要人工改 6 份版本号
- 任意一个正式 Release 都能清楚对出 Git tag、GitHub Release、GHCR 镜像和目标 Alembic head
- 运行中的 FamilyClaw 能明确返回自己的版本元数据
- 数据库升级边界通过 Release 清单表达清楚，而不是靠一套额外手工数据库版本号维持
