# 任务清单 - migpt_xiaoai_speaker 第三方插件（人话版）

状态：In Progress

最近更新（2026-03-23）：

- 宿主 callback 认证会话方案已经撤销，MIGPT 现在只使用宿主通用 `config_preview`、`runtime_state` 和 `preview_artifacts` 能力，不再依赖宿主代管小米二次认证回调。
- 插件前端表单已经改成当前真实主流程：账号字段使用小米账号 ID，帮助说明默认折叠；认证优先导入浏览器 `passToken`，密码只保留为兜底，不再把“手工贴回跳 URL”当正式流程。
- `runtime worker -> MiNA query -> 宿主 text_turn -> 小爱播报 -> heartbeat/禁用/降级` 代码链路已经补到可运行形态并补了测试；但真实账号/真实设备联调还没完整收口，`custom_audio_url` 也还没有稳定的宿主音频 URL 契约。

## 这份任务清单是干什么的

这份清单的目的很单纯：

- 不让我们把 `mi-gpt` 的小米细节重新写回宿主。
- 不让我们把文本轮询方案硬说成音频实时方案。
- 不让我们在插件里再堆一坨不可维护的机型特判。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等待复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：明确取消，并写清原因

---

## 阶段 1：先把插件边界和骨架立起来

- [ ] 1.1 定义第三方插件 manifest、入口和宿主调用边界
  - 状态：DONE
  - 这一步到底做什么：把 `migpt_xiaoai_speaker` 作为第三方插件该声明什么、哪些入口负责什么、哪些宿主能力允许调用先写死。
  - 做完以后你能看到什么：这个插件从第一天起就是“插件”，不是“半插件半核心特例”。
  - 先依赖什么：`005.9`
  - 开始前先看：
    - `requirements.md` 需求 1、需求 7
    - `design.md` §2.1
    - `design.md` §3.3
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/manifest.json`
    - `plugins-dev/migpt_xiaoai_speaker/...`
    - 插件开发文档
  - 这一阶段先不做什么：先不接小米云。
  - 怎么算完成：
    1. manifest 和入口语义清楚。
    2. 宿主调用边界只剩 `speaker/voice` 正式接口。
  - 怎么验证：
    - manifest 校验
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §2.1、§3.3

- [ ] 1.2 建立实例配置模型和机型 profile 基础结构
  - 状态：DONE
  - 这一步到底做什么：先把账号配置、轮询参数、TTS 模式和机型指令 profile 的数据结构立起来。
  - 做完以后你能看到什么：后面接入新型号时，主要改 profile，不是改主流程。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5
    - `design.md` §3.2.1
    - `design.md` §3.2.2
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/config.py`
    - `plugins-dev/migpt_xiaoai_speaker/model_profiles.py`
    - 相关测试文件
  - 这一阶段先不做什么：先不启动常驻轮询。
  - 怎么算完成：
    1. 实例配置能表达账号和运行参数。
    2. profile 能表达机型差异和能力降级。
  - 怎么验证：
    - 配置校验测试
    - profile 命中测试
  - 对应需求：`requirements.md` 需求 1、需求 5
  - 对应设计：`design.md` §3.2.1、§3.2.2

### 阶段检查

- [ ] 1.3 确认插件骨架已经独立成立
  - 状态：DONE
  - 这一步到底做什么：确认现在这个插件哪怕还没接完小米云，也已经是一套独立边界清楚的插件骨架。
  - 做完以后你能看到什么：后面补小米逻辑时不会再回头改宿主边界。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：插件目录和当前 Spec
  - 这一阶段先不做什么：不扩大范围到 UI 细节。
  - 怎么算完成：
    1. 插件目录职责已经分清。
    2. 没有再要求宿主为小米开私有口子。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §2.1、§6.1

---

## 阶段 2：接入小米账号和设备发现

- [ ] 2.1 实现小米账号认证和会话维护
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把登录、会话有效性检测、失效恢复和基础错误语义做出来。
  - 做完以后你能看到什么：插件能够稳定拿到可用的小米客户端，而不是每次业务调用都临时拼登录逻辑。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6
    - `design.md` §2.3.1
    - `design.md` §2.3.5
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/xiaomi_auth.py`
    - `plugins-dev/migpt_xiaoai_speaker/runtime_worker.py`
    - 相关测试文件
  - 这一阶段先不做什么：先不提交 text turn。
  - 怎么算完成：
    1. 认证成功、失败、失效三种状态清楚。
    2. 风控和异常不会静默吞掉。
  - 怎么验证：
    - 认证状态测试
    - heartbeat 状态测试
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` §2.3.1、§2.3.5

- [ ] 2.2 实现候选设备发现和正式绑定接入
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把小米账号下的小爱音箱转成宿主正式候选设备，并走正式绑定主链。
  - 做完以后你能看到什么：用户可以像接别的集成一样，看到候选音箱并完成绑定。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §2.3.2
    - `design.md` §4.1
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/device_discovery.py`
    - `plugins-dev/migpt_xiaoai_speaker/integration.py`
    - 相关测试文件
  - 这一阶段先不做什么：先不做轮询对话。
  - 怎么算完成：
    1. 候选设备能列出来。
    2. 绑定结果带正式 `plugin_id + integration_instance_id`。
  - 怎么验证：
    - discovery / binding 集成测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §2.3.2、§4.1

### 阶段检查

- [ ] 2.3 确认设备发现不再依赖宿主小米特例
  - 状态：IN_PROGRESS
  - 这一步到底做什么：复核发现和绑定是不是完全由插件产出，宿主只走正式主链。
  - 做完以后你能看到什么：后面接更多新型号时，只需要继续改插件。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 7
    - `design.md` §6.1
  - 主要改哪里：插件实现和相关回归测试
  - 这一阶段先不做什么：不开始补动作执行。
  - 怎么算完成：
    1. 宿主侧没有小米发现分支。
    2. 绑定链路全部是正式主链。
  - 怎么验证：
    - grep
    - 人工审查
  - 对应需求：`requirements.md` 需求 2、需求 7
  - 对应设计：`design.md` §6.1

---

## 阶段 3：实现文本轮询型实时对话

- [ ] 3.1 实现会话轮询、游标管理和幂等提交
  - 状态：IN_REVIEW
  - 这一步到底做什么：把 MiNA 会话轮询出来的新 query 变成宿主正式 `text turn`，并保证不会重复提交。
  - 做完以后你能看到什么：音箱上来的每条新请求都会干净进入宿主实时对话主链。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §2.3.3
    - `design.md` §3.2.3
    - `design.md` §3.2.4
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/runtime_worker.py`
    - `plugins-dev/migpt_xiaoai_speaker/text_turn_bridge.py`
    - 相关测试文件
  - 这一阶段先不做什么：不宣称支持原始音频。
  - 怎么算完成：
    1. 新消息能提交到宿主。
    2. 重复轮询不会生成重复 turn。
  - 怎么验证：
    - text turn 集成测试
    - 幂等测试
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §2.3.3、§6.2、§6.3

- [ ] 3.2 实现宿主回复播报和连续对话模拟
  - 状态：IN_PROGRESS
  - 这一步到底做什么：根据宿主回复结果选择小米 TTS 或音频 URL 播放，并处理长文本和连续对话的现实限制。
  - 做完以后你能看到什么：用户能在音箱上听到 FamilyClaw 的回复，而且知道这是一套文本轮询方案。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` §2.3.3
    - `design.md` §2.3.5
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/runtime_worker.py`
    - `plugins-dev/migpt_xiaoai_speaker/model_profiles.py`
    - 相关测试文件
  - 这一阶段先不做什么：不改宿主 TTS 体系。
  - 怎么算完成：
    1. 文本回复能播。
    2. 长文本和播放状态检查可以调优。
    3. 插件仍只声明 `text_turn`。
  - 怎么验证：
    - 播放逻辑测试
    - profile 覆盖测试
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` §2.3.3、§6.3

### 阶段检查

- [ ] 3.3 确认首版没有假装成音频插件
  - 状态：IN_REVIEW
  - 这一步到底做什么：复核 manifest、文档和运行时实现，确认首版只走文本轮询车道。
  - 做完以后你能看到什么：不会再有人误以为这已经是原始音频实时对话。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md` 需求 3
    - `design.md` §6.3
  - 主要改哪里：插件 manifest、文档、测试
  - 这一阶段先不做什么：不扩范围做音频会话。
  - 怎么算完成：
    1. manifest 没有声明 `audio_session`。
    2. 文档明确写成“文本轮询型实时对话”。
  - 怎么验证：
    - manifest 检查
    - 文档人工走查
  - 对应需求：`requirements.md` 需求 3
  - 对应设计：`design.md` §6.3

---

## 阶段 4：实现统一动作、健康状态和收口

- [ ] 4.1 实现统一 `speaker` 动作翻译和执行
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把宿主的统一动作翻译成 MiNA / MIoT 调用，并按标准结果模型返回。
  - 做完以后你能看到什么：设备控制继续走宿主主链，但小米指令细节仍留在插件。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` §2.3.4
    - `design.md` §3.3.4
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/action_executor.py`
    - `plugins-dev/migpt_xiaoai_speaker/model_profiles.py`
    - 相关测试文件
  - 这一阶段先不做什么：不新增宿主私有动作。
  - 怎么算完成：
    1. 统一动作能执行。
    2. 机型差异通过 profile 处理。
  - 怎么验证：
    - 动作执行测试
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` §2.3.4、§3.3.4

- [ ] 4.2 补齐 heartbeat、禁用拦截和风控恢复
  - 状态：IN_PROGRESS
  - 这一步到底做什么：把 runtime 心跳、禁用停止、登录失效、风控降级全部做完整。
  - 做完以后你能看到什么：插件不再是“能跑就跑，跑挂了没人知道”的脏实现。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §2.3.5
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
    - `docs/开发设计规范/20260316-后端事件循环与周期任务开发规范.md`
  - 主要改哪里：
    - `plugins-dev/migpt_xiaoai_speaker/runtime_worker.py`
    - `plugins-dev/migpt_xiaoai_speaker/xiaomi_auth.py`
    - 相关测试文件
  - 这一阶段先不做什么：不扩展到宿主 UI 改版。
  - 怎么算完成：
    1. runtime 状态可观测。
    2. 禁用后轮询和控制都会停。
    3. 风控、失效、恢复路径清楚。
  - 怎么验证：
    - heartbeat / 禁用 / 降级测试
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §2.3.5、§4.2

### 最终检查

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这个插件已经能独立成立，而且没有反向污染宿主。
  - 做完以后你能看到什么：后续再接别的免刷机音箱方案时，可以照这个模式继续做。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：插件目录、测试、当前 Spec
  - 这一阶段先不做什么：不把未完成内容硬标 DONE。
  - 怎么算完成：
    1. 小米逻辑都留在插件内。
    2. 宿主只剩正式 `speaker/voice` 通用能力。
    3. 首版文本轮询方案验证闭环。
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
    - grep
    - 集成测试
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
