# 任务清单 - 项目版本治理与 GitHub Release 发布（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来堆术语的，是拿来让人快速知道：

- 先把版本事实源收在哪里
- 再怎么把发布链路打通
- 运行时版本信息怎么暴露
- 数据库 schema 兼容信息怎么跟 Release 对上

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且状态已回写
- `CANCELLED`：取消，不做了，但要写原因

---

## 阶段 1：把版本真相收口

- [ ] 1.1 建立根版本源和同步脚本
  - 状态：TODO
  - 这一阶段到底做什么：在仓库根目录新增唯一的 `VERSION` 文件，并补一套脚本把版本同步到 Python 和 Node 的对外版本文件里。
  - 做完你能看到什么：以后发版时只改一个地方，脚本能把其余版本落点一次性改对。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 3.1
    - `design.md` 6.1
  - 主要改哪里：
    - `/VERSION`
    - `/package.json`
    - `/apps/api-server/pyproject.toml`
    - `/apps/open-xiaoai-gateway/pyproject.toml`
    - `/apps/user-app/package.json`
    - `/packages/user-core/package.json`
    - `/packages/user-platform/package.json`
    - `/packages/user-ui/package.json`
    - `/scripts/version/`
  - 这一阶段先不做什么：先不碰 GitHub Actions，也先不做前端显示。
  - 怎么算完成：
    1. 根目录有唯一版本文件
    2. 有可重复执行的同步脚本
    3. 同步后所有纳管版本字段一致
  - 怎么验证：
    - 运行版本同步脚本
    - 运行版本一致性检查脚本
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` 3.1、3.5

- [ ] 1.2 清理后端运行时版本来源
  - 状态：TODO
  - 这一阶段到底做什么：把后端运行时版本从手工写死值改成优先读取构建元数据，避免 `settings.app_version` 和真实 Release 漂移。
  - 做完你能看到什么：后端版本不再靠某个硬编码字符串假装自己是正式版。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1
    - `requirements.md` 需求 3
    - `design.md` 3.1.2
    - `design.md` 3.4
  - 主要改哪里：
    - `/apps/api-server/app/core/config.py`
    - `/apps/api-server/app/main.py`
    - `/apps/api-server/app/core/`
  - 这一阶段先不做什么：先不新增设置页展示。
  - 怎么算完成：
    1. 后端存在统一的版本元数据读取入口
    2. 缺失正式构建元数据时会明确降级成开发信息
  - 怎么验证：
    - 本地单元测试
    - 手动请求根接口和版本接口
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` 3.1、3.4、5.3

### 阶段检查

- [ ] 1.3 版本真相收口检查
  - 状态：TODO
  - 这一阶段到底做什么：确认应用版本已经真正收口到一个源，而不是表面上加了个 `VERSION`，底下还偷偷各写各的。
  - 做完你能看到什么：后续发布流程可以建立在稳定版本事实源上，不会一开始就带着脏状态往前冲。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：阶段 1 涉及的全部版本文件和脚本
  - 这一阶段先不做什么：不新增发布能力，只检查基础是否站稳。
  - 怎么算完成：
    1. 纳管文件版本全部一致
    2. 后端运行时版本来源已统一
    3. 已知漂移点被列清楚并收口
  - 怎么验证：
    - 版本一致性检查脚本
    - 人工走查关键文件
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` 2.1、3.1、6.1

---

## 阶段 2：把 GitHub Release 发布链路打通

- [ ] 2.1 建立 Release 清单生成逻辑
  - 状态：TODO
  - 这一阶段到底做什么：实现 `release-manifest.json` 生成器，把版本、提交、镜像和 schema head 绑到一份结构化文件里。
  - 做完你能看到什么：以后每次发版都有一份机器可读、人工也看得懂的发布清单。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `requirements.md` 需求 4
    - `design.md` 3.2
    - `design.md` 4.1
  - 主要改哪里：
    - `/scripts/version/`
    - `/apps/api-server/migrations/`
    - `/docs/`
  - 这一阶段先不做什么：先不做在线更新检查。
  - 怎么算完成：
    1. 可以从仓库生成 `release-manifest.json`
    2. 清单至少包含应用版本、Git SHA、镜像标签和 schema heads
    3. 能表达是否需要人工迁移
  - 怎么验证：
    - 本地生成一次清单
    - 校验 JSON 结构和字段完整性
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` 3.2、4.1、6.2、6.3

- [ ] 2.2 建立版本守卫和 Release 工作流
  - 状态：TODO
  - 这一阶段到底做什么：把 tag 校验、版本同步校验、镜像构建、Release 清单上传和 GitHub Release 创建放进 GitHub Actions。
  - 做完你能看到什么：以后打 `vX.Y.Z` tag 就能得到一套可追溯的正式发布产物。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `requirements.md` 需求 5
    - `design.md` 3.3
    - `design.md` 3.5
  - 主要改哪里：
    - `/.github/workflows/`
    - `/scripts/version/`
    - `/Dockerfile`
    - `/docker/` 或后续容器构建目录
  - 这一阶段先不做什么：先不做自动升级，也不做版本服务。
  - 怎么算完成：
    1. 存在版本守卫工作流
    2. 存在正式 Release 工作流
    3. 正式工作流能产出镜像和 Release 清单
  - 怎么验证：
    - 在测试 tag 上跑一轮 Actions
    - 检查 GitHub Release 和 GHCR 产物
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 3.3、3.5、5.3

### 阶段检查

- [ ] 2.3 发布链路检查
  - 状态：TODO
  - 这一阶段到底做什么：确认 tag、Release、镜像和清单真的能对上，而不是流水线看着成功，产物却互相对不齐。
  - 做完你能看到什么：发布链路可以作为以后所有 Docker 发版的固定基线。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：阶段 2 涉及的工作流、脚本和构建文件
  - 这一阶段先不做什么：不追加新能力，只核对追踪链是否闭合。
  - 怎么算完成：
    1. Git tag、Release、镜像和清单一致
    2. Release 清单字段完整
    3. 失败路径会明确阻断
  - 怎么验证：
    - 选一次测试发布演练
    - 人工核对 Release 资产和镜像标签
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 2.3、3.2、3.3、3.5

---

## 阶段 3：把运行时版本和升级边界讲清楚

- [x] 3.1 提供系统版本接口并接入前端展示
  - 状态：DONE
  - 当前进度：已完成。后端 `GET /api/v1/system/version` 已落地，前端设置页已接成“版本与更新”用户视图。界面按普通家庭用户口径收敛为两件事：现在是不是最新版本、新版本主要改了什么；不再暴露提交号、构建通道这类工程字段。更新提醒现已直接读取 GitHub Release 结果，仓库地址收口在代码内置常量里，后续切仓只改一处。
  - 这一阶段到底做什么：新增后端系统版本接口，并在用户端设置页用普通用户能看懂的方式展示当前版本、更新提醒和更新说明入口。
  - 做完你能看到什么：排查问题时不用再让人去猜容器里跑的是什么版本。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` 3.4
    - `design.md` 5.2
  - 主要改哪里：
    - `/apps/api-server/app/api/v1/router.py`
    - `/apps/api-server/app/api/v1/endpoints/`
    - `/apps/api-server/app/core/version_metadata.py`
    - `/apps/user-app/src/pages/settings/`
    - `/packages/user-core/`
  - 这一阶段先不做什么：先不做自动下载安装，也不做额外的版本服务。
  - 怎么算完成：
    1. 后端可返回结构化版本信息
    2. 前端设置页能展示关键版本字段
    3. 更新提醒直接基于 GitHub Release 真实结果
  - 怎么验证：
    - 接口测试
    - 前端人工检查
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` 3.4、5.2

- [ ] 3.2 落地 schema 兼容记录和人工迁移边界
  - 状态：TODO
  - 这一阶段到底做什么：把应用版本与 schema head 的关系、允许从哪些旧 schema 升级、是否需要人工迁移这几件事落到 Release 清单和配套文档里。
  - 做完你能看到什么：未来升级应用时，至少能清楚知道它期望把数据库带到哪里，以及什么时候该人工介入。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` 3.2.3
    - `design.md` 4.1
    - `../001.7-PostgreSQL数据库迁移/`
  - 主要改哪里：
    - `/scripts/version/`
    - `/apps/api-server/migrations/`
    - `/docs/开发者文档/后端/`
    - 当前 Spec 的 `docs/`
  - 这一阶段先不做什么：不再发明新的独立数据库主版本号。
  - 怎么算完成：
    1. Release 清单可表达 schema heads 和升级边界
    2. 人工迁移场景有明确记录位置
    3. 文档明确拒绝“051”这类平行数据库主版本号方案
  - 怎么验证：
    - 生成一份带 schema 字段的 Release 清单
    - 人工走查迁移说明文档
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` 3.2、4.1、6.3

### 最终检查

- [ ] 3.3 最终验收
  - 状态：TODO
  - 这一阶段到底做什么：确认版本治理这件事不是只做了半截脚本，而是真的把版本源、发布链路、运行时展示和 schema 兼容记录串起来了。
  - 做完你能看到什么：后续别人接手时，能顺着文档和产物直接看懂怎么发版、怎么追版本、怎么判断数据库升级边界。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件以及实现中涉及的脚本、工作流和接口
  - 这一阶段先不做什么：不再扩需求，只做收口和验收。
  - 怎么算完成：
    1. 根版本源、Release、镜像和运行时版本信息能互相对上
    2. 数据库 schema 关系有结构化记录
    3. 关键风险和人工边界写清楚
  - 怎么验证：
    - 按 `design.md` 7.4 的映射逐项核对
    - 走一轮测试发布和运行时查询
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
