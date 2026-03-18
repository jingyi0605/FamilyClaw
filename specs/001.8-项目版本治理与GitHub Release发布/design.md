# 设计文档 - 项目版本治理与 GitHub Release 发布

状态：Draft

## 1. 概览

### 1.1 目标

- 把应用版本收口成一个唯一事实源
- 让 Git tag、GitHub Release、GHCR 镜像和运行时版本信息形成同一条追踪链
- 让数据库 schema 继续以 Alembic revision 为真相，同时补齐“哪个应用版本对应哪个 schema head、支持从哪里升级”的发布元数据
- 在不新增服务器的前提下，把发布流程收口成可执行的 CI/CD 方案

### 1.2 覆盖需求

- `requirements.md` 需求 1：统一应用版本事实源
- `requirements.md` 需求 2：GitHub Release 成为发布事实源
- `requirements.md` 需求 3：运行中的应用必须能自报家门
- `requirements.md` 需求 4：应用版本与数据库 schema 关系必须可追踪
- `requirements.md` 需求 5：不额外部署服务器也能完成发布治理
- `requirements.md` 需求 6：版本规则必须和现有插件宿主兼容性机制兼容

### 1.3 技术约束

- 后端：FastAPI + Python 3.11 + Alembic + PostgreSQL
- 前端：Taro H5 + npm workspace
- 发布产物：Docker 镜像为主，未来可扩展前端多端产物
- 发布基础设施：仅允许使用 GitHub、GitHub Actions、GitHub Release、GHCR
- 数据库 schema 版本：必须继续以 Alembic revision / head 为准，不能绕开迁移系统

## 2. 架构

### 2.1 系统结构

版本治理收口为五个角色：

1. 根版本源：仓库根目录 `VERSION`
2. 版本同步器：把根版本同步到 Python / Node 配置和构建元数据
3. Release 构建器：根据 tag 产出镜像、Release 清单和 GitHub Release
4. 运行时版本提供器：把镜像内嵌的版本元数据暴露给 API 和前端
5. Schema 兼容记录器：在 Release 清单中记录 Alembic head 和升级边界

整体关系如下：

`VERSION` -> 同步脚本 -> 子项目版本文件 -> Git tag -> GitHub Actions -> GHCR 镜像 + Release 清单 -> GitHub Release -> 运行时版本接口 / 设置页展示

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 根版本源 | 维护唯一应用版本文本 | `VERSION` 文件 | 版本号 |
| 版本同步脚本 | 把根版本写回各子项目配置 | 根版本、配置文件列表 | 已同步的 `package.json` / `pyproject.toml` |
| Release 清单生成器 | 产出发布元数据 | 版本号、Git SHA、镜像信息、Alembic heads | `release-manifest.json` |
| GitHub Actions 发布流 | 校验版本、构建、推送镜像、创建 Release | Git tag、仓库内容、Secrets | Release、镜像、资产 |
| 运行时版本服务 | 对外暴露版本信息 | 镜像内嵌元数据 | API 响应、前端显示 |

### 2.3 关键流程

#### 2.3.1 正式发布流程

1. 维护者修改根目录 `VERSION`
2. 运行版本同步脚本，更新需要对外暴露的版本文件
3. 提交并合并到 `main`
4. 创建 `vX.Y.Z` 或 `vX.Y.Z-rc.N` tag
5. GitHub Actions 校验 tag 与 `VERSION` 一致
6. 工作流构建前端、后端和 Docker 镜像
7. 工作流读取 Alembic head，生成 Release 清单
8. 工作流推送 GHCR 镜像并创建 GitHub Release

#### 2.3.2 容器运行时版本查询流程

1. 镜像构建时写入一份内嵌版本元数据文件
2. `api-server` 启动时读取该元数据
3. 后端通过系统版本接口返回应用版本、Git SHA、构建时间、Release 链接和 schema 目标
4. 前端设置页调用该接口并展示版本信息

#### 2.3.3 数据库 schema 兼容追踪流程

1. 发布工作流读取当前仓库 Alembic head 列表
2. Release 清单记录 `schema_heads`
3. 如果本次发布存在人工迁移或升级边界，额外写入 `upgrade_policy`
4. 启动脚本继续执行 `alembic upgrade head`
5. 运维和排查人员通过 Release 清单判断“这版应用目标 schema 是什么、从哪些旧库升级是被支持的”

## 3. 组件和接口

### 3.1 版本源设计

覆盖需求：1、2、6

#### 3.1.1 根版本源

- 文件：`/VERSION`
- 内容：单行版本文本，例如 `0.3.0`
- 规则：
  - 不带前缀 `v`
  - 允许预发布后缀，例如 `0.4.0-rc.1`
  - 必须满足现有宿主版本比较规则能够解析，避免插件兼容逻辑失真

#### 3.1.2 需要被同步的版本落点

第一批纳管这些文件：

- `/apps/api-server/pyproject.toml`
- `/apps/open-xiaoai-gateway/pyproject.toml`
- `/apps/user-app/package.json`
- `/packages/user-core/package.json`
- `/packages/user-platform/package.json`
- `/packages/user-ui/package.json`

`settings.app_version` 不再手工写死为新的正式版本值，而是改为：

1. 优先读取构建时注入或镜像内嵌的版本信息
2. 开发环境缺失时回退到开发默认值，例如 `0.0.0-dev`

### 3.2 Release 清单

覆盖需求：2、3、4、5

#### 3.2.1 设计原则

Release 清单不是一段人看着大概明白的说明，而是一份机器可读、人工也能看懂的发布事实记录。

它必须解决这几个问题：

1. 这个应用版本对应哪个 Git 提交
2. 这个应用版本对应哪个镜像标签
3. 这个应用版本期望的 schema head 是什么
4. 这个应用版本是否允许从某些旧版本直接升级
5. 是否存在人工迁移步骤

#### 3.2.2 `release-manifest.json`

建议结构如下：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `app_version` | string | 是 | 应用版本 | 与 `VERSION` 一致 |
| `git_tag` | string | 是 | Git tag | 形如 `v0.3.0` |
| `git_sha` | string | 是 | 提交 SHA | 不可为空 |
| `release_url` | string | 是 | GitHub Release 链接 | 指向当前 Release |
| `docker_image` | string | 是 | GHCR 精确镜像标签 | 不可使用 `latest` |
| `built_at` | string | 是 | 构建时间 | ISO 8601 |
| `schema_heads` | string[] | 是 | 目标 Alembic head 列表 | 至少 1 项 |
| `upgrade_policy.min_supported_app_version` | string/null | 否 | 最低支持直接升级的应用版本 | SemVer |
| `upgrade_policy.allowed_source_schema_heads` | string[] | 否 | 允许直接升级的源 schema heads | 可为空 |
| `upgrade_policy.requires_manual_migration` | boolean | 是 | 是否需要人工迁移 | 默认 `false` |
| `upgrade_policy.manual_migration_doc` | string/null | 否 | 人工迁移说明链接 | 为空表示无 |

#### 3.2.3 为什么这里不用独立数据库版本号

这次明确拒绝把数据库版本设计成独立的 `051`、`052` 之类主编号，原因有四个：

1. Alembic revision 已经是可执行的 schema 版本事实源
2. 多个应用版本可以合法共享同一个 schema head
3. merge revision、分叉收口等情况不适合用单个整数概括
4. 再维护一套手工编号，只会制造漂移点

结论：

- **应用版本 -> schema heads**：需要显式记录
- **schema heads -> 数据库真实状态**：继续由 Alembic 管
- **独立数据库版本号 051**：不采用

如果后续确实需要更易读的展示字段，可以提供派生字段，例如 `schema_label`，但它只能是展示别名，不能变成兼容判断主事实源。

### 3.3 GitHub Release 与镜像标签契约

覆盖需求：2、5

#### 3.3.1 Git tag

- 稳定版：`vX.Y.Z`
- 预发布：`vX.Y.Z-rc.N`

#### 3.3.2 镜像标签

- 精确标签：`ghcr.io/<org>/familyclaw:X.Y.Z`
- 预发布标签：`ghcr.io/<org>/familyclaw:X.Y.Z-rc.N`
- 提交标签：`ghcr.io/<org>/familyclaw:sha-<shortsha>`
- 浮动标签：
  - `X.Y`
  - `X`
  - `latest` 仅稳定版更新

规则：

- 回滚和问题排查只使用精确标签
- `latest` 只是便利入口，不能当审计依据

### 3.4 运行时版本接口

覆盖需求：3、5

#### 3.4.1 后端接口

- 类型：HTTP
- 路径：`GET /api/v1/system/version`
- 输入：无
- 输出：

```json
{
  "app_version": "0.3.0",
  "git_tag": "v0.3.0",
  "git_sha": "abc1234",
  "built_at": "2026-03-18T12:00:00Z",
  "release_url": "https://github.com/org/repo/releases/tag/v0.3.0",
  "docker_image": "ghcr.io/org/familyclaw:0.3.0",
  "schema_heads": ["20260318_0052"],
  "upgrade_policy": {
    "min_supported_app_version": "0.2.0",
    "allowed_source_schema_heads": ["20260317_0051"],
    "requires_manual_migration": false,
    "manual_migration_doc": null
  },
  "build_channel": "release"
}
```

- 校验：
  - 元数据缺失时不能伪造稳定版信息
  - 开发环境允许返回 `build_channel=development`

#### 3.4.2 前端展示

设置页至少展示：

- 当前应用版本
- 当前提交短 SHA
- 发布渠道（稳定版 / 预发布 / 开发版）
- 当前 Release 链接
- 目标 schema heads 或简化后的 schema 信息

### 3.5 CI/CD 设计

覆盖需求：1、2、4、5

发布工作流建议拆成两层：

#### 3.5.1 版本守卫工作流

职责：

- 校验 `VERSION` 格式
- 校验所有被纳管文件的版本是否已同步
- 校验 tag 是否等于 `v${VERSION}`

#### 3.5.2 Release 工作流

职责：

- 构建前端产物
- 构建 Docker 多架构镜像
- 读取 Alembic heads
- 生成 `release-manifest.json`
- 推送 GHCR
- 创建 GitHub Release
- 上传 Release 资产

## 4. 数据与状态模型

### 4.1 数据关系

本 Spec 里的关键关系只有三条：

1. 一个应用版本对应一个 Git tag
2. 一个应用版本对应一个 Release 清单
3. 一个应用版本对应一组目标 schema heads，而不是一个手工数据库版本号

关系图用人话说就是：

- `VERSION` 决定应用版本
- Git tag 固化发布点
- Release 清单把应用版本和 schema 目标绑起来
- 数据库自身实际版本由 `alembic_version` 表反映

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `draft` | 版本已修改但未发布 | 修改 `VERSION` | 创建 tag |
| `tagged` | 版本已打 tag，准备发布 | 创建 Git tag | Release 工作流成功或失败 |
| `released` | Release、镜像和清单都已生成 | 工作流全部成功 | 进入下一次发布周期 |
| `failed` | 发布失败，需要修复 | 任一关键步骤失败 | 重新发起发布 |

## 5. 错误处理

### 5.1 错误类型

- 版本源格式错误
- 子项目版本未同步
- Git tag 与根版本不一致
- Release 清单缺字段
- Alembic head 读取失败
- 运行时版本元数据缺失

### 5.2 错误响应格式

```json
{
  "detail": "版本元数据不完整，当前无法确认正式发布信息。",
  "error_code": "version_metadata_missing",
  "field": "release-manifest.json",
  "timestamp": "2026-03-18T00:00:00Z"
}
```

### 5.3 处理策略

1. 版本源格式错误：CI 直接失败
2. 子项目版本未同步：CI 或本地同步校验直接失败
3. Release 清单缺字段：阻断 GitHub Release 创建
4. 运行时元数据缺失：接口返回开发/未知状态，不伪造正式信息
5. 人工迁移要求未声明：禁止把该 Release 标记为可安全升级

## 6. 正确性属性

### 6.1 单一事实源

对于任何正式发布版本，系统都应满足：仓库内只有一个应用版本主事实源，其他所有版本字段都是同步结果或派生结果。

**验证需求：** `requirements.md` 需求 1

### 6.2 发布可追溯

对于任何正式 Release，系统都应满足：Git tag、Release 清单、GHCR 镜像和运行时版本接口能互相对出同一个应用版本和同一个提交。

**验证需求：** `requirements.md` 需求 2、需求 3

### 6.3 Schema 真相不重复发明

对于任何应用 Release，系统都应满足：数据库 schema 真相仍由 Alembic revision / head 表达，Release 只记录兼容边界，不再额外创造平行数据库主版本号。

**验证需求：** `requirements.md` 需求 4

## 7. 测试策略

### 7.1 单元测试

- 版本格式解析
- 版本同步脚本替换逻辑
- Release 清单生成逻辑
- 运行时版本元数据读取逻辑

### 7.2 集成测试

- Tag 与 `VERSION` 一致性校验
- 构建流程生成 `release-manifest.json`
- 后端版本接口返回镜像内嵌元数据

### 7.3 端到端测试

- 从 tag 到 GitHub Release 的完整演练
- 容器启动后通过 API 和前端页面看到一致的版本信息
- 带 schema 变化的 Release 演练清单输出

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 3.1、3.5 | 本地脚本校验 + CI |
| `requirements.md` 需求 2 | `design.md` 3.2、3.3、3.5 | Tag 发布演练 |
| `requirements.md` 需求 3 | `design.md` 3.4 | API 测试 + 前端人工检查 |
| `requirements.md` 需求 4 | `design.md` 3.2、4.1 | Release 清单校验 |
| `requirements.md` 需求 5 | `design.md` 2.3、3.5 | CI 配置检查 |
| `requirements.md` 需求 6 | `design.md` 3.1、3.2 | 插件版本比较回归测试 |

## 8. 风险与待确认项

### 8.1 风险

- 现有 `settings.app_version` 与多处静态版本字段已经被业务逻辑使用，收口时容易漏掉一个角落
- GitHub Actions 和 GHCR Secrets 缺失会让首轮发布流程卡死
- 预发布版本格式如果和插件版本比较规则不一致，会影响宿主兼容判断

### 8.2 待确认项

- 第一版是否要同时落前端设置页版本展示，还是先只做后端版本接口
- Release 清单是否只作为 GitHub Release 资产，还是同时提交到仓库某个目录做长期归档
