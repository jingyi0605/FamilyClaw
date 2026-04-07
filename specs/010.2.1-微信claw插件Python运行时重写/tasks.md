# 任务清单 - 微信claw插件Python运行时重写（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只做一件事：把“微信插件从 Node 子层迁回 Python”这件事拆成可以真正执行的步骤，避免最后变成一堆零散补丁。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每做完一个任务，必须立刻更新这里

---

## 阶段 1：先把边界钉死，别再摇摆

- [x] 1.1 建立 Python 重写 Spec 并冻结迁移目标
  - 状态：DONE
  - 这一步到底做什么：新建 `010.2.1` 子 Spec，明确这次不是“给 Docker 装 Node”，而是“把微信插件后端彻底迁回 Python”。
  - 做完你能看到什么：新的 `requirements.md`、`design.md`、`tasks.md` 已经建立，后面不会再围着“要不要继续留 Node”打转。
  - 先依赖什么：无
  - 开始前先看：
    - `specs/010.2-微信claw第三方通道插件/README.md`
    - `specs/010.2-微信claw第三方通道插件/design.md`
    - `specs/000-Spec规范/Spec模板/`
  - 主要改哪里：
    - `specs/010.2.1-微信claw插件Python运行时重写/README.md`
    - `specs/010.2.1-微信claw插件Python运行时重写/requirements.md`
    - `specs/010.2.1-微信claw插件Python运行时重写/design.md`
    - `specs/010.2.1-微信claw插件Python运行时重写/tasks.md`
  - 这一步先不做什么：先不动插件运行代码，也不改 Docker。
  - 怎么算完成：
    1. 已明确写出 Node 方案为什么退出历史舞台
    2. 已明确写出 Python 重写的范围、边界和验收方向
  - 怎么验证：
    - 人工检查 Spec 文件是否齐全且能读懂
  - 对应需求：`requirements.md` 需求 1、需求 5
  - 对应设计：`design.md` §1、§2
  - 本次回写补充：
    1. 已新建 `010.2.1` 子 Spec，明确宿主不再为微信插件背 Node 运行时
    2. 已把“插件后端逻辑必须使用 Python 完成”写入本次需求和设计目标

- [x] 1.2 盘清旧 Node 子层到底替插件做了什么
  - 状态：DONE
  - 这一步到底做什么：把当前 `plugin/bridge.py + vendor/weixin_transport/` 的登录、轮询、发送、媒体和二维码逻辑逐项列出来，做成迁移清单。
  - 做完你能看到什么：后面每一段 Python 重写都有明确对照，不会漏掉隐蔽能力。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4
    - `design.md` §2.1「系统结构」
    - `design.md` §3.3「接口契约」
    - `apps/api-server/plugins-dev/weixin_claw_channel/vendor/weixin_transport/`
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/bridge.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/vendor/weixin_transport/`
    - `specs/010.2.1-微信claw插件Python运行时重写/docs/`
  - 这一步先不做什么：先不改接口实现，只做盘点和对照。
  - 怎么算完成：
    1. 登录、状态刷新、轮询、发送、媒体、二维码链路都有迁移条目
    2. 每条迁移条目都能指向旧实现入口
  - 怎么验证：
    - 人工走查
    - 代码检索
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` §2.1、§3.3、§4.1
  - 本次回写补充：
    1. 已新增 `docs/20260407-Node子层能力盘点.md`
    2. 已确认旧 Node 子层实际承担了登录、状态刷新、轮询、文本发送、媒体加解密、二维码生成和上游 HTTP 协议封装
    3. 已确认 Python 重写不能只迁登录链路，必须连 `poll/send/media/context_token` 一起收口

### 阶段检查

- [x] 1.3 边界检查点
  - 状态：DONE
  - 这一步到底做什么：确认重写边界已经钉死，不再出现“先保留 Node 兼容一下”这种后退设计。
  - 做完你能看到什么：后面代码实施只剩执行问题，不再是方向问题。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不提前开始实现。
  - 怎么算完成：
    1. 迁移范围和不做事项都清楚
    2. 没有保留双栈长期共存的含糊表述
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 5
  - 对应设计：`design.md` §1、§2、§6.2
  - 本次回写补充：
    1. 已确认本次方向是“纯 Python 重写”，不是“保留 Node 兼容”
    2. 已明确 Node bridge 和 Node transport 都只属于待迁移旧方案，不是长期保留项

---

## 阶段 2：把正式运行链路迁回 Python

- [x] 2.1 建立 Python transport 骨架并接通登录链路
  - 状态：DONE
  - 这一步到底做什么：新增 Python transport 服务，先接通 `start_login` 和 `get_login_status`，让二维码生成和登录状态刷新不再经过 Node。
  - 做完你能看到什么：扫码登录主链路已经能在纯 Python 条件下跑通。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3
    - `design.md` §2.3「扫码登录」
    - `design.md` §3.1「核心组件」
    - `design.md` §3.3「接口契约」
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/action.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/config_preview.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/python_transport.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/`
  - 这一步先不做什么：先不动消息轮询和发送。
  - 怎么算完成：
    1. `start_login` 不再依赖 Node 进程
    2. `get_login_status` 不再依赖 Node 进程
    3. 现有 `preview_artifacts + runtime_state` 契约保持不变
  - 怎么验证：
    - 插件定向测试
    - 纯 Python 容器或无 Node 环境验证
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2.3、§3.1、§3.3
  - 本次回写补充：
    1. 已新增 `plugin/python_transport.py` 和 `plugin/weixin_api_client.py`
    2. `start_login` 和 `get_login_status` 已改为纯 Python 实现
    3. 二维码预览已改为 Python 侧生成 SVG data URL，不再经过 Node

- [x] 2.2 迁移消息轮询、文本发送、媒体和 context_token
  - 状态：DONE
  - 这一步到底做什么：把 `poll/send` 从 Node 子层迁到 Python，同时保住去重、游标、附件和 `context_token` 恢复。
  - 做完你能看到什么：微信插件正式收发链路已经回到 Python，一条完整主链路闭合。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` §2.3「消息轮询与发送」
    - `design.md` §4.1「数据关系」
    - `design.md` §4.2「状态流转」
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/channel.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/runtime_state.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/python_transport.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/`
  - 这一步先不做什么：先不删除旧 Node 目录，避免影响比对和回归。
  - 怎么算完成：
    1. `poll` 和 `send` 不再经过 Node bridge
    2. 轮询游标、事件去重和 `context_token` 恢复仍然可用
    3. 第一版已支持的基础媒体没有被重写过程搞坏
  - 怎么验证：
    - 单元测试
    - 集成测试
    - 真实链路回放
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3、§4.1、§4.2、§5.3
  - 本次回写补充：
    1. `poll/send` 已改为纯 Python transport 实现
    2. 入站媒体下载、出站附件上传、AES-ECB 处理和 `context_token` 链路已迁回 Python
    3. `channel.py` 和 `action.py` 的宿主调用面保持不变

### 阶段检查

- [x] 2.3 Python 主链路检查点
  - 状态：DONE
  - 这一步到底做什么：确认纯 Python 实现已经覆盖登录、轮询、发送主流程，不再靠 Node 子层兜底。
  - 做完你能看到什么：已经不是“写了一半”，而是一条能运行的正式链路。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不提前做文档收尾和发布动作。
  - 怎么算完成：
    1. 纯 Python 环境下主要流程可验证
    2. 关键异常路径已有结构化处理
  - 怎么验证：
    - 关键流程回放
    - 容器环境验证
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3、§3.3、§4.2、§6.1、§6.2
  - 本次回写补充：
    1. 定向测试已覆盖 `bridge/action/channel/config_preview/runtime_state/python_transport/manifest`
    2. 当前本地回归结果为 `26 passed`
    3. 正式运行链路已经不再依赖 Node 进程

---

## 阶段 3：清理旧方案，补齐文档和验收

- [x] 3.1 删除 Node 运行依赖并更新插件手册
  - 状态：DONE
  - 这一步到底做什么：删掉正式运行不再需要的 Node bridge 和 Node transport 依赖，更新微信插件手册与插件开发规则。
  - 做完你能看到什么：代码、README、开发规范都指向同一个事实：插件后端用 Python，不再双栈。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5
    - `design.md` §1.1「目标」
    - `design.md` §6.2「运行时单语言收口」
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/README.md`
    - `apps/api-server/plugins-dev/weixin_claw_channel/package.json`
    - `apps/api-server/plugins-dev/weixin_claw_channel/vendor/`
    - 插件开发相关正式文档
  - 这一步先不做什么：不再继续扩展微信能力范围。
  - 怎么算完成：
    1. 正式运行链路不再依赖 Node 目录和 Node 说明
    2. 文档明确写出插件后端逻辑必须使用 Python
  - 怎么验证：
    - 代码检索
    - 文档走查
  - 对应需求：`requirements.md` 需求 1、需求 5
  - 对应设计：`design.md` §1.1、§2.1、§6.2
  - 本次回写补充：
    1. 已删除插件根目录 `package.json` 和旧 `vendor/weixin_transport` Node 源码
    2. 已更新微信插件 README，明确插件后端只使用 Python
    3. 已更新正式开发文档，明确插件后端逻辑和代码必须使用 Python 完成

### 最终检查

- [ ] 3.2 最终检查点
  - 状态：IN_REVIEW
  - 这一步到底做什么：确认这次重写真的把问题解决了，而不是把 Node 相关说明从报错里换到了文档脚注里。
  - 做完你能看到什么：需求、设计、任务、实现和验证证据全部对上。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件和微信插件正式代码
  - 这一步先不做什么：不再追加新需求。
  - 怎么算完成：
    1. 微信插件纯 Python 运行链路已验证
    2. 文档和代码都不再把 Node 当成正式依赖
    3. 后续接手的人能看懂为什么这么改、改到了哪一步
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
  - 本次回写补充：
    1. 代码、README、开发文档和 Spec 已同步更新
    2. 还差一轮真实部署镜像的验收回放，确认新依赖和容器构建链一致
