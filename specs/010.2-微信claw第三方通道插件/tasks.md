# 任务清单 - 微信claw第三方通道插件

状态：Draft

## 说明

这份任务清单只做一件事：把微信 claw 插件从“POC 已经能跑”变成“可以正式开发”的执行路径写清楚。

这里不允许出现两种垃圾：

- 只写“做插件化改造”这种废话，不写具体产物
- 明明会改宿主，却不先把“哪些宿主改动是通用能力，哪些绝对禁止”写清楚

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等待复核
- `DONE`：已经完成并同步回写
- `CANCELLED`：明确取消，不再继续

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 只要任务状态变化，就必须立刻回写这份文档
- 如果被卡住，卡点必须写清楚，别装死

---

## 阶段 1：把边界定死

- [x] 1.1 定稿插件边界、目录和 manifest 方案
  - 状态：DONE
  - 这一项到底做什么：把微信插件必须落在 `plugins-dev`、必须是第三方插件包、必须声明哪些类型和入口，全部写死
  - 做完你能看到什么：后续实现不会再争论“是不是可以塞进宿主核心”
  - 先依赖什么：当前 `010`、`010.1` 和本 Spec 草案
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6
    - `design.md` 2.1、3.1、3.2.1
  - 主要改哪里：
    - `specs/010.2-微信claw第三方通道插件/requirements.md`
    - `specs/010.2-微信claw第三方通道插件/design.md`
  - 这一项先不做什么：先不写具体实现代码，先不碰宿主逻辑
  - 怎么算完成：
    1. 插件目录、插件 ID、插件类型、入口文件和配置作用域已经定稿
    2. 明确写出宿主禁止出现的微信逻辑清单
  - 怎么验证：
    - 人工通读文档，检查有没有模糊描述
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` 2.1、3.1、6.1

- [x] 1.2 盘点宿主需要补齐的通用能力
  - 状态：DONE
  - 这一项到底做什么：确认扫码动作、账号级动作、状态摘要、插件 `working_dir` 等哪些是宿主通用能力，哪些不能做成微信特判
  - 做完你能看到什么：宿主改动范围清楚，后面不会借着“通用能力”偷塞微信代码
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` 2.2、3.3、4.1
  - 主要改哪里：
    - `specs/010.2-微信claw第三方通道插件/design.md`
    - `specs/010.2-微信claw第三方通道插件/tasks.md`
  - 这一项先不做什么：不实现宿主页面，只做缺口盘点和边界确认
  - 怎么算完成：
    1. 宿主新增项都可以被其他第三方插件复用
    2. 不存在任何“只给微信用”的宿主接口设计
  - 怎么验证：
    - 设计评审
    - 核对每一项宿主改动是否能脱离微信成立
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` 2.2、3.3、4.1、8.2

### 阶段检查

- [x] 1.3 边界检查点
  - 状态：DONE
  - 这一项到底做什么：只检查边界是不是已经收紧，不再继续扩大范围
  - 做完你能看到什么：可以进入实现阶段，而不是带着结构性烂问题往前冲
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部文档
  - 这一项先不做什么：不追加新需求
  - 怎么算完成：
    1. 插件边界、宿主边界、禁止项已经写清楚
    2. 宿主和插件分工不存在相互打架的地方
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` 2.1、2.2、4.1、6.1

---

## 阶段 2：搭插件骨架和桥接层

- [x] 2.1 建立微信插件包骨架
  - 状态：DONE
  - 这一项到底做什么：在 `apps/api-server/plugins-dev/weixin_claw_channel/` 下创建 manifest、Python 入口、Node vendor 目录和测试骨架
  - 做完你能看到什么：插件能被宿主识别，目录结构不再是临时脚本堆
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 3.1、3.2.1
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/manifest.json`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/`
    - `apps/api-server/plugins-dev/weixin_claw_channel/vendor/`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/`
  - 这一项先不做什么：先不打通真实登录和收发
  - 怎么算完成：
    1. 宿主能发现该插件并识别 `channel`、`action` 入口
    2. 插件骨架自检测试可跑
  - 怎么验证：
    - 插件发现测试
    - manifest 校验测试
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 3.1、3.2.1

- [x] 2.2 实现 Python 到 Node 的桥接协议
  - 状态：DONE
  - 这一项到底做什么：把宿主 Python 插件入口和 Node transport 调用打通，统一请求和错误返回格式
  - 做完你能看到什么：Python 插件已经能稳定调用 Node transport，而不是靠人工脚本联调
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` 2.2、3.3、5.1
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/bridge.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/vendor/weixin_transport/`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/test_bridge.py`
  - 这一项先不做什么：先不优化成长驻守护进程
  - 怎么算完成：
    1. `poll`、`send`、`action` 三类请求都能通过同一桥接协议调用
    2. Node 失败时能返回结构化错误，而不是一坨 stderr
  - 怎么验证：
    - 桥接单测
    - 假 transport 集成测试
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` 2.2、3.3、5.1

### 阶段检查

- [x] 2.3 骨架检查点
  - 状态：DONE
  - 这一项到底做什么：确认插件包已经站稳，后面不会一改实现就把结构改烂
  - 做完你能看到什么：插件目录、桥接协议、测试入口都稳定了
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关文件
  - 这一项先不做什么：不引入新的能力范围
  - 怎么算完成：
    1. 插件骨架已经够后续功能继续迭代
    2. Python 和 Node 的职责边界已经稳定
  - 怎么验证：
    - 人工走查
    - 基础测试回归
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` 2.2、3.1、3.3

---

## 阶段 3：做登录态和私有状态持久化

- [x] 3.1 打通扫码登录和登录状态查询
  - 状态：DONE
  - 这一项到底做什么：实现 `start_login`、`get_login_status`、`logout` 等动作，把扫码登录从 POC 搬进正式插件
  - 做完你能看到什么：管理员可以在正式插件里完成扫码登录和状态查看
  - 本次回写补充：Node transport 不再把微信返回的 H5 扫码页地址直接当图片地址返回；插件现在本地把扫码目标 URL 生成为 SVG data URL，再通过通用 `artifacts/preview_artifacts` 图片渲染链路展示二维码
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.3.1、3.3.2、4.2.1
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/action.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/models.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/test_action.py`
  - 这一项先不做什么：先不做复杂后台自动续期
  - 怎么算完成：
    1. 二维码生成、扫码完成、状态查询、主动退出都可用
    2. 登录态不会只存在内存里
  - 怎么验证：
    - 人工扫码测试
    - 登录状态集成测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` 2.3.1、3.2.3、3.3.2、4.2.1

- [x] 3.2 落地插件私有运行目录和 SQLite 状态存储
  - 状态：DONE
  - 这一项到底做什么：实现 `working_dir` 初始化、SQLite 建表、媒体目录、日志目录和状态读写封装
  - 做完你能看到什么：登录态、游标、`context_token`、日志都有稳定落盘位置
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` 3.2.3、4.1、4.2.2
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/runtime_state.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/logging_utils.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/test_runtime_state.py`
  - 这一项先不做什么：先不做多节点共享状态
  - 怎么算完成：
    1. 账号登录态、轮询游标、`context_token` 都能稳定落盘
    2. 插件重启后可以恢复关键状态
  - 怎么验证：
    - 重启恢复测试
    - SQLite 读写单测
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 3.2.3、4.1、4.2.2、6.2

### 阶段检查

- [ ] 3.3 状态持久化检查点
  - 状态：DONE
  - 这一项到底做什么：确认最危险的那块状态问题已经不再靠内存硬扛
  - 做完你能看到什么：插件可以承受重启和延迟回复，不再一断进程就失忆
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/20260323-POC验证与风险结论.md`
  - 主要改哪里：本阶段相关文件
  - 这一项先不做什么：不扩展额外媒体类型
  - 怎么算完成：
    1. `context_token` 恢复方案已经被实现和验证
    2. 登录态和游标恢复都跑通
  - 怎么验证：
    - 人工重启回归
    - 自动化恢复测试
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 2.3.4、3.2.3、4.2.2、6.2

---

## 阶段 4：打通收发主链路

- [x] 4.1 打通 `poll` 入站和幂等处理
  - 状态：DONE
  - 这一项到底做什么：实现正式的 `poll` 入口，把微信消息稳定标准化后送进宿主现有 `channel` 入站链路
  - 做完你能看到什么：微信收消息不再依赖 demo，而是走正式插件
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` 2.3.2、3.3.1、5.3
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/channel.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/test_channel.py`
  - 这一项先不做什么：先不做 webhook 主模式
  - 怎么算完成：
    1. `poll` 能输出宿主标准事件
    2. 重复消息不会重复入站
  - 怎么验证：
    - 轮询集成测试
    - 实机收消息验证
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` 2.3.2、3.3.1、5.3

- [x] 4.2 打通文本发送、`context_token` 恢复和基础媒体
  - 状态：DONE
  - 这一项到底做什么：实现正式的 `send` 入口，把文本发送、token 恢复、媒体上传下载接起来
  - 做完你能看到什么：微信正式插件可以收文本、发文本，并支持第一版定义的基础媒体
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 2.3.3、2.3.4、3.2.3、5.3
  - 主要改哪里：
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/channel.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/plugin/runtime_state.py`
    - `apps/api-server/plugins-dev/weixin_claw_channel/tests/test_channel.py`
  - 这一项先不做什么：先不扩展全部媒体类型
  - 怎么算完成：
    1. 文本发送稳定可用
    2. `context_token` 缺失、失效、恢复三种场景都有明确行为
    3. 第一版定义的媒体类型可上传下载
  - 怎么验证：
    - 实机收发测试
    - token 恢复测试
    - 媒体链路测试
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` 2.3.3、2.3.4、3.2.3、5.3、6.2

### 阶段检查

- [ ] 4.3 主链路检查点
  - 状态：TODO
  - 这一项到底做什么：确认正式插件已经具备“能收、能发、能恢复”的最小闭环
  - 做完你能看到什么：可以从 POC 进入实际开发联调阶段
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关文件
  - 这一项先不做什么：不扩大 UI 范围
  - 怎么算完成：
    1. 正式插件已经替代 demo 完成核心收发闭环
    2. 关键失败路径都有日志和错误码
  - 怎么验证：
    - 实机联调
    - 自动化集成测试
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 5
  - 对应设计：`design.md` 2.3.2、2.3.3、2.3.4、5.1、5.3

---

## 阶段 5：管理、文档和合规收口

- [x] 5.1 补齐通用管理入口和状态展示
  - 状态：DONE
  - 这一项到底做什么：如果宿主缺少账号级插件动作、状态摘要或日志入口，就只补齐通用能力，不写微信特判
  - 做完你能看到什么：管理员能在正式界面完成扫码登录、看状态、看失败摘要
  - 本次回写补充：宿主已移除 MiGPT / open_xiaoai 前端特异文案和特判逻辑；插件表单文案改为由插件自己的 `manifest + locales` 提供
  - 本次回写补充：`channel-access` 已补齐通用 `ui_schema.actions + runtime_sections + preview_artifacts` 渲染；微信扫码登录现在通过插件声明的账号级动作、状态区和二维码预览正式接入
  - 本次回写补充：宿主通用 artifact schema 已补齐 `data:image/...` 图片 data URL 支持；正式页面之前看不到二维码，不是前端不渲染，而是正式 schema 还把图片 URL 长度卡死在 2048
  - 本次回写补充：宿主通用 `plugin-config-auth` 回调基址解析已补齐 `Settings.base_url`；即使未配置 `FAMILYCLAW_BASE_URL`，也会安全退回当前请求 `base_url`，不再因为缺字段导致 `config/preview` 直接 500
  - 本次回写补充：Spec 和正式文档已补齐两项宿主后端通用能力的正式说明：一是 `plugin-config-auth` 配置认证会话，二是 `channel.send` 的统一媒体 delivery 契约；文档里已经写清什么场景该用、走哪些接口、请求体和返回体最小长什么样
  - 先依赖什么：4.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` 2.1、3.3.2、4.1
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/channel/`
    - 相关前端页面和通用组件
  - 这一项先不做什么：不在宿主页面写死微信字段
  - 怎么算完成：
    1. 通用入口足以驱动微信插件的登录和状态管理
    2. 宿主代码里没有微信专属文案和逻辑分支
  - 怎么验证：
    - 代码评审
    - 人工操作回归
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` 2.1、3.3.2、4.1、6.1

- [ ] 5.2 完成来源说明、风险说明和发布前检查
  - 状态：TODO
  - 这一项到底做什么：把上游来源、许可证、技术风险、平台条款待确认项、联调说明都补成正式文档
  - 做完你能看到什么：项目不是“能跑但说不清”，而是能解释来源和风险
  - 先依赖什么：5.1
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` 8.1、8.2
    - `docs/20260323-POC验证与风险结论.md`
  - 主要改哪里：
    - `specs/010.2-微信claw第三方通道插件/docs/`
    - 相关正式项目文档
  - 这一项先不做什么：不替法务做最终裁决，只把事实和待确认项写清楚
  - 怎么算完成：
    1. 来源、许可证、技术风险和待确认法律风险都已落文档
    2. 实现和文档边界一致
  - 怎么验证：
    - 文档走查
    - 发布前清单核对
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` 8.1、8.2

### 最终检查

- [ ] 5.3 最终检查点
  - 状态：TODO
  - 这一项到底做什么：确认这个 Spec 真能指导开发，而不是看起来完整、实际一落地就打架
  - 做完你能看到什么：需求、设计、任务、风险和补充文档都能一一对上
  - 先依赖什么：5.1、5.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一项先不做什么：不追加新需求
  - 怎么算完成：
    1. 每个任务都能追到需求和设计
    2. 风险和待确认项没有遗漏
    3. 后续接手的人知道先看哪里、先做什么
  - 怎么验证：
    - 按 Spec 清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
