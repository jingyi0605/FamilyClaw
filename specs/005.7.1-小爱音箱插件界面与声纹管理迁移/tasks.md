# 任务清单 - 小爱音箱插件界面与声纹管理迁移

状态：DONE

## 这份文档是干什么的

这次最容易写成垃圾的地方，不是不会写页面，而是：

- 又把小爱专属字段加回 `Device`
- 又在宿主前端加一层 `if (pluginId === 'open-xiaoai-speaker')`
- 又把“通用声纹能力”和“小爱私有配置”搅成一团

这份任务清单的目的只有一个：

- 先把边界和数据结构立住
- 再把宿主页签和配置入口接起来
- 最后把旧硬编码收掉

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每做完一个任务，必须立刻回写这里
- 兼容层如果暂时保留，必须写清楚退出条件

---

## 阶段 1：先把设备详情边界钉死

- [x] 1.1 盘清当前设备详情里哪些是小爱私货，哪些是平台通用能力
  - 状态：DONE
  - 这一步到底做什么：把现有 `Device` 字段、宿主前端弹层、声纹页签和语音接管逻辑逐项盘清，确认哪些必须迁到插件页签，哪些必须留在平台通用页签。
  - 做完你能看到什么：后面不会再拿“小爱历史实现”冒充正式设备详情边界。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5、需求 7
    - `design.md` §2.1「系统结构」
    - `design.md` §4.1「数据关系」
  - 主要改哪里：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.7.1-小爱音箱插件界面与声纹管理迁移/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.7.1-小爱音箱插件界面与声纹管理迁移/design.md)
  - 这一步先不做什么：先不改代码，不发明新接口。
  - 怎么算完成：
    1. 文档里能清楚说出“小爱私货”和“平台通用能力”的分界线
    2. 文档里明确写出哪些旧实现属于迁移目标
  - 怎么验证：
    - 人工走查 `requirements.md`、`design.md`
  - 对应需求：`requirements.md` 需求 1、需求 5、需求 7
  - 对应设计：`design.md` §2.1、§4.1、§6.1、§6.2

- [x] 1.2 定死首版不做远程插件前端加载
  - 状态：DONE
  - 这一步到底做什么：明确首版插件页签只支持“宿主按正式配置协议渲染表单”，不搞插件下发 bundle 和远程组件执行。
  - 做完你能看到什么：实现不会被过度设计拖死。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` §2.3.2「打开小爱语音接管页签」
    - `design.md` §3.2.1「PluginManifestDeviceDetailTabSpec」
  - 主要改哪里：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.7.1-小爱音箱插件界面与声纹管理迁移/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.7.1-小爱音箱插件界面与声纹管理迁移/design.md)
  - 这一步先不做什么：不去设计第二套插件 UI 平台。
  - 怎么算完成：
    1. 文档明确写出首版 `render_mode = config_form`
    2. 文档明确写出为什么不做远程 bundle
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.2、§3.2.1、§3.3.2

### 阶段检查

- [x] 1.3 检查边界有没有写成空话
  - 状态：DONE
  - 这一步到底做什么：确认文档能直接回答“哪个页签归插件、哪个页签归平台、为什么”，而不是堆术语。
  - 做完你能看到什么：后面做任务时不需要再猜边界。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部主文档
  - 这一步先不做什么：不加新范围。
  - 怎么算完成：
    1. 能一眼看懂插件页签与通用页签的职责
    2. 首版实现边界足够具体
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4、需求 5
  - 对应设计：`design.md` §2、§3、§4

---

## 阶段 2：补齐后端正式扩展点和设备级配置

- [x] 2.1 给插件 manifest 增加设备详情页签声明
  - 状态：DONE
  - 这一步到底做什么：在插件 manifest 和注册表 schema 里补正式的设备详情页签声明，让插件能说“我在哪些设备上显示哪个页签”。
  - 做完你能看到什么：宿主终于有正式元数据可消费，而不是继续靠插件 id 硬编码。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` §3.2.1「PluginManifestDeviceDetailTabSpec」
    - `design.md` §3.1「核心组件」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/service.py`
    - 小爱插件 manifest
  - 这一步先不做什么：先不改前端渲染。
  - 怎么算完成：
    1. manifest 能声明设备详情页签
    2. 注册表返回里带出该声明
  - 怎么验证：
    - 后端单元测试
    - 读取插件注册表结果人工检查
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §3.1、§3.2.1、§3.3.1

- [x] 2.2 给插件配置协议增加设备级作用域
  - 状态：DONE
  - 这一步到底做什么：把正式配置作用域扩到 `device`，或者实现等价的正式设备级配置实例，避免继续偷用 `plugin` 作用域。
  - 做完你能看到什么：小爱专属设备配置终于有正式落点。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` §3.2.2「DevicePluginConfigInstance」
    - `design.md` §5.3「处理策略」
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/config_service.py`
    - `apps/api-server/app/modules/plugin/models.py`
    - Alembic migration
  - 这一步先不做什么：先不删旧 `Device` 字段。
  - 怎么算完成：
    1. 后端能按设备读取和保存插件配置
    2. 旧配置作用域语义没有继续被污染
  - 怎么验证：
    - 后端测试
    - migration upgrade 测试
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` §3.2.2、§3.3.2、§3.3.3、§6.1、§6.3

- [x] 2.3 给设备详情补能力快照和页签聚合接口
  - 状态：DONE
  - 这一步到底做什么：提供设备详情聚合视图，把设备能力、插件页签、通用页签一次性返回给前端。
  - 做完你能看到什么：前端不再自己猜“这个设备该显示哪些页签”。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` §3.2.3「DeviceDetailViewRead」
    - `design.md` §3.3.1「获取设备详情聚合视图」
  - 主要改哪里：
    - `apps/api-server/app/modules/device/service.py`
    - 设备详情相关 endpoint / schema
    - 相关测试
  - 这一步先不做什么：先不动前端交互。
  - 怎么算完成：
    1. 聚合接口能返回页签和能力
    2. 不支持语音终端的设备不会被错误标成支持声纹
  - 怎么验证：
    - 后端集成测试
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` §3.2.3、§3.3.1、§4.2.1、§4.2.2

### 阶段检查

- [x] 2.4 检查后端扩展点是不是正式的，不是偷映射
  - 状态：DONE
  - 这一步到底做什么：复核 manifest、配置作用域和聚合接口是不是都走正式模型，没有再偷拿旧字段硬拼。
  - 做完你能看到什么：前端接入时面对的是稳定协议，不是临时凑起来的假接口。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩新需求。
  - 怎么算完成：
    1. 设备页签声明和设备级配置可以被稳定消费
    2. 没有继续把 `plugin` 作用域偷当设备作用域
  - 怎么验证：
    - 代码走查
    - 测试验证
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 6
  - 对应设计：`design.md` §3、§4、§6

---

## 阶段 3：把宿主设备详情切到新边界

- [x] 3.1 改造设备详情容器，统一按页签模型渲染
  - 状态：DONE
  - 这一步到底做什么：把现有设备详情弹层改造成统一页签容器，插件页签和通用页签都走同一套标签页框架。
  - 做完你能看到什么：宿主不再内建“小爱专属弹层结构”。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 7
    - `design.md` §2.3.1「打开设备详情」
    - `design.md` §3.1「核心组件」
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
  - 这一步先不做什么：先不删旧字段兼容逻辑。
  - 怎么算完成：
    1. 设备详情可以同时承接插件页签和通用页签
    2. 标签页显示顺序和显隐都由后端视图模型驱动
  - 怎么验证：
    - 前端组件测试
    - 人工打开设备详情检查
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §2.3.1、§3.1、§3.3.1

- [x] 3.2 把小爱语音接管迁到插件页签
  - 状态：DONE
  - 这一步到底做什么：把现有小爱语音接管表单从宿主专属组件迁到“插件页签 + 统一表单 renderer”。
  - 做完你能看到什么：小爱专属配置终于回到插件体系。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6
    - `design.md` §2.3.2「打开小爱语音接管页签」
    - `design.md` §3.3.2、§3.3.3
  - 主要改哪里：
    - 小爱插件 manifest
    - `apps/user-app/src/pages/settings/components/`
    - 插件设备配置接口
  - 这一步先不做什么：先不删兼容字段。
  - 怎么算完成：
    1. 小爱设备详情能看到插件专属“语音接管”页签
    2. 保存后走正式设备级插件配置接口
  - 怎么验证：
    - 前后端联调
    - 组件测试
  - 对应需求：`requirements.md` 需求 4、需求 6
  - 对应设计：`design.md` §2.3.2、§3.2.1、§3.2.2、§3.3.2、§3.3.3

- [x] 3.3 把声纹管理迁到平台通用页签，并改成按能力判断显示
  - 状态：DONE
  - 这一步到底做什么：把现有声纹页签从“小爱详情特例”改成“平台通用语音终端页签”，显示逻辑只看设备能力。
  - 做完你能看到什么：声纹管理不再绑死在小爱专属弹层上。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` §2.3.3「打开声纹管理页签」
    - `design.md` §6.2「通用声纹页签不能依赖单个插件存在」
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/SpeakerVoiceprintTab.tsx`
    - 设备详情容器
    - 相关测试
  - 这一步先不做什么：不改声纹业务接口协议。
  - 怎么算完成：
    1. 小爱设备还能看到声纹管理
    2. 普通 speaker 但不支持语音终端的设备不会看到声纹管理
  - 怎么验证：
    - 前端测试
    - 人工检查多种设备详情
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` §2.3.3、§3.2.3、§6.2

### 阶段检查

- [x] 3.4 检查前端是不是已经不再靠小爱特例活着
  - 状态：DONE
  - 这一步到底做什么：复核设备详情页签组合、显示条件和保存路径，确认主链已经切到正式协议。
  - 做完你能看到什么：可以开始做兼容清理，而不是继续两套结构并行。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不急着删旧字段。
  - 怎么算完成：
    1. 宿主不再按小爱插件 id 直接写死设备详情结构
    2. 声纹页签显示逻辑不再只看 `speaker`
  - 怎么验证：
    - grep
    - 组件测试
    - 人工复核
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 7
  - 对应设计：`design.md` §2.3、§4.2、§6

---

## 阶段 4：兼容迁移和旧代码清理

- [x] 4.1 补齐新配置与旧字段的兼容同步
  - 状态：DONE
  - 这一步到底做什么：把设备级插件配置和旧 `Device` 字段之间的兼容读写规则补齐，保证迁移期间运行链路不断。
  - 做完你能看到什么：新入口能用，旧运行链也不会马上断。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §5.3「处理策略」
    - `design.md` §6.3「迁移期间不能破坏现有运行链路」
  - 主要改哪里：
    - `apps/api-server/app/modules/device/service.py`
    - `apps/api-server/app/modules/voice/binding_service.py`
    - 相关测试
  - 这一步先不做什么：先不删旧字段。
  - 怎么算完成：
    1. 新配置优先，旧字段兜底的顺序明确
    2. 语音接管和声纹相关现有链路继续可用
  - 怎么验证：
    - 后端集成测试
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §3.2.2、§5.3、§6.3

- [x] 4.2 删除与新边界冲突的宿主硬编码
  - 状态：DONE
  - 这一步到底做什么：把旧的小爱专属设备详情分支、按 `speaker/vendor` 粗暴判断的分支、重复组件入口清理掉。
  - 做完你能看到什么：仓库里只剩一条清晰边界。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` §2.1「系统结构」
    - `design.md` §6.1「插件私有配置不能再污染通用设备模型」
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/components/`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
  - 这一步先不做什么：不删除仍被运行链明确依赖的兼容字段。
  - 怎么算完成：
    1. 宿主前端里不再有“小爱详情特例主链”
    2. 设备详情显隐逻辑只消费正式协议和能力快照
  - 怎么验证：
    - grep
    - 前端测试
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` §2.1、§3.1、§6.1、§6.2

### 阶段检查

- [x] 4.3 检查兼容层有没有写清退出条件
  - 状态：DONE
  - 这一步到底做什么：确认保留的旧字段和兼容逻辑都有明确退出时机，不会永久留着。
  - 做完你能看到什么：这次迁移不是把垃圾换个地方藏起来。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 和兼容实现相关文件
  - 这一步先不做什么：不追加新兼容层。
  - 怎么算完成：
    1. 每个保留的兼容点都写清原因和退出条件
    2. 没有“以后再说”的永久过渡逻辑
  - 怎么验证：
    - 人工走查
    - grep 自检
  - 对应需求：`requirements.md` 需求 6、需求 7
  - 对应设计：`design.md` §5.3、§6.3、§8

---

## 阶段 5：验证、文档和最终收口

- [x] 5.1 补齐关键测试和验收清单
  - 状态：DONE
  - 这一步到底做什么：把页签声明、设备级配置、能力判断、兼容迁移这些关键链路补齐测试。
  - 做完你能看到什么：这次不是“看起来像改好了”，而是真能证明没破坏主链。
  - 先依赖什么：4.3
  - 开始前先看：
    - `requirements.md` 全部需求
    - `design.md` §7「测试策略」
  - 主要改哪里：
    - 前后端相关测试文件
    - 必要的联调说明文档
  - 这一步先不做什么：不启动开发服务器。
  - 怎么算完成：
    1. 关键路径都有测试或明确人工验证方式
    2. 新旧边界相关回归点都有清单
  - 怎么验证：
    - 测试命令
    - 人工验收
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §7

- [x] 5.2 最终检查点
  - 状态：DONE
  - 这一步到底做什么：确认需求、设计、任务、验证证据和兼容退出条件都能一一对上。
  - 做完你能看到什么：别人接手时能直接看懂这次迁移怎么做、做到了哪一步。
  - 先依赖什么：5.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再加新需求。
  - 怎么算完成：
    1. 关键任务都能追踪到需求和设计
    2. 兼容层和删除条件写清楚
    3. 后续接手的人能一眼看懂
  - 怎么验证：
    - 按 Spec 逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

---

## 补记：2026-03-17 声纹录入卡在准备中的热修

- 现象：前端创建声纹录入任务后，页面一直停在“录入进行中 / 准备中 / 0/3”，但后端和网关都没有后续录音日志。
- 真正原因：任务虽然已经写进数据库，但在线小爱网关没有及时拿到新的 `pending_voiceprint_enrollment`，现场实际过度依赖 discovery claim poll 的下一轮刷新。
- 修复做法：
  - 后端新增 `binding.refresh` 实时命令。
  - 创建录入、取消录入、录入样本推进、录入失败这几个状态变化点，都会主动把最新 terminal binding 推给在线网关。
  - 网关收到 `binding.refresh` 后，会直接热更新当前 terminal context 里的 `pending_voiceprint_enrollment`，不再等下一轮轮询。
- 这次修复明确不做什么：不改前端轮询协议，不改声纹 provider，不再继续堆更多兜底轮询。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voiceprints_api`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`

---

## 补记：2026-03-17 声纹录入三轮引导流程落地

- 现象：即便上一轮已经修掉了“任务创建后网关无感知”，录入流程本身仍然是半成品。用户只能盯着 0/3、1/3 的进度数字，不知道现在该读什么，也听不到明确节奏提示。
- 这次真正补上的东西：
  - 后端在创建 enrollment 时，如果前端没传 `expected_phrase`，会自动给这次录入分配一条稳定的默认短句，保证前端和网关始终拿得到朗读内容。
  - 后端新增声纹录入提示服务，按“先 TTS 提示，再播放提示音”的方式下发每轮引导，不新开协议，继续走现有 `play.start`。
  - 创建任务后立即播第一轮提示；每轮录入成功但还没满 3 轮时，自动播下一轮提示；样本被拒绝时，自动播当前轮重试提示。
  - 前端等待页改成真正的朗读卡片，直接显示当前句子、当前轮次和三步操作说明，不再让用户自己猜流程。
- 这次明确不做什么：
  - 不改前端轮询协议。
  - 不做“三轮三句不同短句”的复杂编排，首版先固定一句话循环 3 轮。
  - 不让音响直接念出屏幕上的句子，避免把提示语污染进声纹样本。
- 顺手修掉的真 bug：
  - 同步 endpoint 里 `anyio.from_thread.run()` 之前是错用关键字参数，实际有概率根本没把异步通知发出去。
  - 现在统一改成闭包调用，确保 `binding.refresh` 和声纹引导提示都真的能发到运行中的事件循环。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m py_compile C:\Code\FamilyClaw\apps\api-server\app\api\v1\endpoints\voiceprints.py C:\Code\FamilyClaw\apps\api-server\app\modules\voice\pipeline.py C:\Code\FamilyClaw\apps\api-server\app\modules\voiceprint\service.py C:\Code\FamilyClaw\apps\api-server\app\modules\voiceprint\prompt_service.py C:\Code\FamilyClaw\apps\api-server\tests\test_voiceprints_api.py C:\Code\FamilyClaw\apps\api-server\tests\test_voiceprint_prompt_service.py`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voiceprints_api tests.test_voiceprint_prompt_service`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`
  - `cd C:\Code\FamilyClaw\apps\user-app && npm.cmd run test:voiceprint`

---

## 补记：2026-03-17 声纹录入卡死任务自动收口

- 现象：如果之前有一个 enrollment 已经过期，但状态还挂在 `pending / recording / processing`，前端会一直卡在“录入进行中”，用户既关不掉，也开不了新的录入任务。
- 真正原因：
  - 前端 waiting 态没有“结束本次录入”的正式入口，还把弹窗关闭动作硬锁死了。
  - 设备详情页对同一个 enrollment 轮询了两遍，纯属重复代码。
  - 后端没有把过期 enrollment 自动改成终态，导致旧任务一直占着设备坑位。
- 修复做法：
  - 前端 waiting 态增加“结束本次录入”按钮，调用正式取消接口，不再只给一个禁用的“请等待”。
  - 设备详情页删除重复轮询 effect，只保留一份等待态轮询。
  - 后端新增过期 enrollment 收口逻辑，在创建任务、查询任务、读取成员详情、读取家庭汇总、列出任务这些入口先清理过期任务，再继续返回结果。
  - 过期任务统一改成 `cancelled`，并写入 `voiceprint_enrollment_expired`，避免再伪装成“还在进行中”。
- 这次明确不做什么：
  - 不新增另一套“强制结束流程”协议。
  - 不靠前端本地超时假装任务结束。
  - 不让关闭弹窗冒充取消任务。
- 验证命令：
  - `cd C:\Code\FamilyClaw\apps\user-app && npm.cmd run test:voiceprint`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voiceprints_api`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m py_compile app\modules\voiceprint\service.py app\api\v1\endpoints\voiceprints.py`

---

## 补记：2026-03-17 声纹引导实时指令改成正式后台任务投递

- 现象：创建声纹录入任务后，前端能看到 enrollment 已经创建，但 gateway 完全没有收到 `binding.refresh` 和 `play.start`，日志安静得像没发生过事。
- 真正原因：
  - 这条链路之前在同步 endpoint 里用 `anyio.from_thread.run()` 直接把异步实时指令塞回主循环。
  - 这种写法依赖当前请求线程一定带有 AnyIO worker thread 上下文，条件不成立时就会直接跳过。
  - 之前这类跳过还是 `debug` 日志，生产现场用 `INFO` 基本看不到，排查成本高得离谱。
- 修复做法：
  - 录入创建、录入取消这两个同步 endpoint 改成使用 FastAPI `BackgroundTasks` 投递实时副作用。
  - 录入提示使用轻量 snapshot 传参，不再把 ORM 对象生命周期硬绑到后台投递时机上。
  - 后端补了明确日志：成功下发会打印 `dispatched binding refresh` / `dispatched voiceprint round prompt`；没发出去会明确写 terminal offline 或 delivery failed。
- 这次明确不做什么：
  - 不把同步 endpoint 全部粗暴改成 async 再直接跑阻塞 DB。
  - 不新造一套队列系统去解决一个局部实时投递问题。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m py_compile app\api\v1\endpoints\voiceprints.py app\modules\voice\binding_refresh_service.py app\modules\voiceprint\prompt_service.py`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voiceprints_api tests.test_voiceprint_prompt_service`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`

---

## 补记：2026-03-17 声纹录入第一轮不自动结束的网关热修

- 现象：
  - `binding.refresh`、TTS 和提示音已经能到 gateway，但第一轮永远停在 0/3。
  - 日志里只有 `play.start`，没有后续样本提交。
- 真正原因：
  - 之前的实现只把 `pending_voiceprint_enrollment` 当成“如果终端自己发起语音事件，就按 enrollment 处理”的上下文。
  - 但是提示音播完以后，gateway 并不会主动建一轮声纹采集会话，也不会主动在一个固定窗口后提交样本。
  - 结果就是：没有 `session.start`，`record` 音频也不会被转发，第一轮只能一直挂着。
- 修复做法：
  - 声纹引导里的 `beep` 在 gateway 侧增加真实的 3 秒等待，不再只是 TTS 里口头说“3 秒后”。
  - `beep` 播完后，gateway 主动开始一轮声纹采集：
    - 创建 `voiceprint_enrollment` 会话并上报 `session.start`
    - 重新下发一次 `start_recording`，确保录音流处于工作状态
    - 在固定采集窗口结束后自动上报 `audio.commit`
  - 为了让声纹建档稳定收口，commit 会带上 enrollment 的 `expected_phrase` 作为 `debug_transcript` 兜底。
  - 如果这一轮根本没有收到任何音频字节，gateway 不再无限等待，而是明确上报 `session.cancel` 并打出日志。
  - 同时补了状态清理：
    - 绑定刷新时会取消旧的声纹轮次任务
    - 终端断开时会取消未结束的轮次任务
    - 新一轮开始前会清掉旧的声纹会话，避免再次卡死在上一轮
- 这次明确不做什么：
  - 不新增新的后端录入协议。
  - 不把录入时序再塞回前端猜。
  - 不继续依赖终端“也许会自己开一轮录音”这种不可靠行为。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m py_compile apps\open-xiaoai-gateway\open_xiaoai_gateway\bridge.py apps\open-xiaoai-gateway\tests\test_bridge.py`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest apps.open-xiaoai-gateway.tests.test_bridge`

---

## 补记：2026-03-18 第一轮成功后第二轮不播的后端热修

- 现象：
  - 第一轮已经能正常采集并自动 `audio.commit`。
  - 后端状态也能推进到 `1/3`，前端会显示“等待下一轮样本”。
  - 但 gateway 只收到新的 `binding.refresh`，始终收不到第二轮 `play.start`。
- 真正原因：
  - 样本处理函数返回的是 ORM `enrollment` 对象。
  - 第一轮提交完成后，pipeline 一边用它做 `binding.refresh`，一边又继续拿它的 `sample_count/status` 去拼第二轮 prompt。
  - 这在对象已经脱离会话时非常不稳，典型结果就是：`binding.refresh` 发出去了，第二轮 prompt 这边直接炸掉或者静默失败。
- 修复做法：
  - 把声纹提示所需的最小字段抽成正式的 `VoiceprintPromptEnrollmentSnapshot`，放到独立模块里。
  - `process_voiceprint_enrollment_sample()` 返回结果时，同时带上这个 snapshot，不再让后续链路继续碰脱会话 ORM 对象。
  - pipeline 刷新 terminal binding 和下发下一轮 prompt 时，统一优先使用 snapshot 的 `terminal_id/sample_count/status`。
  - 顺手拆掉了原来 `service -> prompt_service -> service` 的循环依赖，避免这条链越修越烂。
- 这次明确不做什么：
  - 不新增另一套“轮次推进事件”协议。
  - 不靠前端自己猜“既然变成 1/3 了，那就本地弹第二轮”。
  - 不继续让 pipeline 读取跨线程返回的 ORM 对象赌运气。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m py_compile app\modules\voiceprint\prompt_types.py app\modules\voiceprint\prompt_service.py app\modules\voiceprint\service.py app\modules\voice\pipeline.py tests\test_voice_pipeline_voiceprint_prompt.py`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voice_pipeline_voiceprint_prompt tests.test_voiceprint_prompt_service tests.test_voiceprint_async_service`

---

## 补记：2026-03-18 网关按 binding.refresh 自循环后续轮次

- 现象：
  - 第一轮采样成功后，前端已经变成 `1/3`，但第二轮提示音和滴声还是没来。
  - 现场日志能看到第一轮结束后的 `binding.refresh`，但没有新的 `play.start`。
- 真正原因：
  - 就算后端已经把第二轮 prompt 发送逻辑补稳，现场依然可能因为实时链路时序、对象生命周期或投递缺口，出现“状态推进了，但下一轮提示没有继续播”的断链。
  - 这种设计本身就太脆，后续轮次不该继续依赖后端每轮都再推一遍完整 `play.start`。
- 修复做法：
  - gateway 收到 `binding.refresh` 且发现 `pending_voiceprint_enrollment` 从 `0/3` 变成 `1/3`、`2/3` 这类“已推进但未完成”的状态后，会直接在本地排队下一轮提示。
  - 本地提示仍然沿用同一套节奏：
    - 先播“请准备第 N 轮”
    - 再等 3 秒
    - 再播滴声
    - 然后自动进入录音窗口并自动 commit
  - 这样后续轮次的推进只依赖 `binding.refresh`，不再依赖 api-server 再补发一整组 `play.start`。
- 这次明确不做什么：
  - 不再把“第二轮一定要等后端 prompt”当作单点依赖。
  - 不把轮次推进交给前端本地计时。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m py_compile open_xiaoai_gateway\bridge.py tests\test_bridge.py`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`

---

## 补记：2026-03-18 重启后续轮补播与调度日志收口

- 现象：
  - gateway 重启后，日志能看到 `claimed terminal activated` 和周期性的 `refreshed active terminal binding`。
  - 但第二轮、第三轮有时就是不继续播，现场只能看到“拿到了 pending enrollment”，看不到为什么没排队。
- 真正原因：
  - 原来的本地续轮调度还在赌 `refresh_reason` 和 `sample_count_changed` 这类时序条件。
  - 这种写法太脆，只要重启、轮询刷新、实时 `binding.refresh` 到达顺序稍微变一下，就可能因为“看起来没变化”而直接跳过。
  - 更糟的是，早退分支几乎没有明确日志，现场只能看到“没播”，根本不知道是被哪条条件挡住。
- 修复做法：
  - gateway 的本地续轮调度改成更笨也更稳的规则：
    - 只要当前还有未完成的 `pending_voiceprint_enrollment`
    - 且没有正在播的音频、没有正在录的声纹会话、没有正在跑的轮次任务
    - 且这轮 `prompt_key` 之前没播过
    - 就直接排本地提示，不再强依赖 `sample_count_changed`
  - 仍然保留 `voiceprint_enrollment_created` 的特殊处理，避免和后端首轮 prompt 重复。
  - 给每个跳过分支补了 `INFO` 日志，把 `refresh_reason`、前后 sample_count、当前播放/会话状态一起打出来，现场以后不会再靠猜。
- 这次明确不做什么：
  - 不再继续增加新的“也许这次能猜对”的条件判断。
  - 不要求前端参与续轮定时。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m py_compile open_xiaoai_gateway\bridge.py tests\test_bridge.py`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`

---

## 补记：2026-03-18 声纹样本提交后的脱会话 ORM 崩溃修复

- 现象：
  - 第一轮录音提交后，gateway 已经能收到 `binding.refresh` 并准备本地续播第二轮。
  - 但 api-server 会立刻把 realtime websocket 打成 `1011`，gateway 随后在发送第二轮 `playback.started` 时撞到已关闭连接。
  - 日志里明确是 `DetachedInstanceError`，炸点在 `result.sample.id`。
- 真正原因：
  - 声纹处理结果虽然已经把 prompt 需要的 enrollment 信息抽成了 snapshot，但 pipeline 里还残留着对 `result.sample.id` / `result.profile.id` 这类 ORM 对象的直接访问。
  - 这些对象一旦离开原来的 Session，就不再可靠，继续碰它们就是在赌 SQLAlchemy 不会反噬。
- 修复做法：
  - `VoiceprintEnrollmentProcessResult` 正式增加 `sample_id` 和 `profile_id` 两个稳定字段。
  - 结果构造时立即把 id 提前拎出来，后续链路不再依赖脱会话 ORM。
  - pipeline 更新路由结果时只读 `result.profile_id or result.sample_id`。
  - 顺手把“第一轮之后继续由 api-server 发后续 prompt”收掉，改成只刷新 binding，由 gateway 本地续轮，减少 realtime 链路的脆弱点。
- 这次明确不做什么：
  - 不再继续让 pipeline 读取 `sample.id`、`profile.id` 这种脱会话字段。
  - 不保留两套“后端续轮”和“网关续轮”并行竞争。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m py_compile app\modules\voice\pipeline.py app\modules\voiceprint\service.py tests\test_voice_pipeline_voiceprint_prompt.py`
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_voice_pipeline_voiceprint_prompt tests.test_voiceprint_prompt_service tests.test_voiceprint_async_service`

---

## 补记：2026-03-18 对话调试日志补齐声纹识别记录

- 现象：
  - 声纹识别结果已经进入语音链路内存态，也能影响后续身份决策。
  - 但打开对话调试日志时，只能看到聊天编排和回复阶段，看不到这次到底把谁识别成了说话人。
- 真正原因：
  - 之前只有 `conversation.service` 内部私有的 `_append_debug_log(...)`。
  - `voice.conversation_bridge` 没有正式入口可调用，所以声纹身份结果一直没落到 `conversation_debug_logs`。
- 修复做法：
  - 在 `conversation.service` 增加正式公开入口 `append_conversation_debug_log(...)`，统一复用现有调试日志落库逻辑。
  - 在语音桥接主链里新增 `voice.identity.resolved` 调试阶段。
  - 日志 payload 会带上：
    - `identity_status`
    - `requester_member_id`
    - `requester_member_name`
    - `requester_member_role`
    - `speaker_confidence`
    - `identity_reason`
    - `voiceprint_hint`
    - `candidates`
    - 以及 `voice_session_id`、`terminal_id`、`transcript_text`
- 这次明确不做什么：
  - 不让 `voice` 模块直接硬调私有函数。
  - 不把声纹识别结果拆成一堆散字段后各处自己拼日志。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\api-server\.venv\Scripts\python.exe -m unittest tests.test_conversation_debug_log_service tests.test_voice_conversation_bridge`

---

## 补记：2026-03-18 网关对 api realtime websocket 重启的收尾加固

- 现象：
  - 语音对话过程中，gateway 偶尔会收到 api-server realtime websocket 的 `1012 service restart` 关闭。
  - 实际上 terminal 很快就能重新 claim 成功，但 gateway 收尾代码还会继续尝试发 `terminal.offline`，并把已关闭 websocket 当成异常抛栈。
  - 现场看起来像“网关崩了”，其实是“断线已恢复，但日志和收尾逻辑很烂”。
- 真正原因：
  - `_forward_api_commands()` 没把 `ConnectionClosed` 视为正常断链。
  - `_handle_terminal_connection()` 的 finally 里又会继续 await 已失败的 `api_reader_task`，并尝试往已关闭 websocket 发送 `terminal.offline`。
- 修复做法：
  - gateway 现在把 api websocket 的 `ConnectionClosed` 视为正常断链，记一条 `INFO`，不再抛异常栈。
  - 如果 websocket 已经关闭，就跳过 `terminal.offline` 上报，不再把可恢复重连打成错误。
  - finally 阶段等待 `api_reader_task` 时，也会吞掉这类已知连接关闭异常。
- 这次明确不做什么：
  - 不伪造“api-server 永远不会重启”这种前提。
  - 不把可恢复 websocket 关闭继续当成 gateway 崩溃。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_bridge`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m py_compile open_xiaoai_gateway\bridge.py tests\test_bridge.py`

---

## 补记：2026-03-18 普通前缀接管对话补齐声纹识别音频留存

- 现象：
  - 声纹录入已经成功，但普通语音对话的调试日志里 `voiceprint_hint.status` 一直是 `not_attempted`。
  - 同一时间段内，`voice-runtime-artifacts` 只有 `voiceprint_enrollment` 样本，没有普通 `conversation` 音频文件。
- 真正原因：
  - `native_first` 模式下，gateway 之前要等最终识别文本命中接管前缀，才会正式发 `session.start`。
  - 这意味着前面 `record` 音频流到达时还没有 `active_session_id`，`audio.append` 全被直接丢掉。
  - api-server 收不到普通对话音频，自然也就没有音频文件给声纹识别服务尝试。
- 修复做法：
  - `native_first` 普通前缀接管在 `is_vad_begin` 时先预热一轮 `conversation` 会话，但不提前打断原生小爱。
  - 这样录音流可以先正常转成 `audio.append`，把普通对话音频留到 runtime 里。
  - 等最终文本出来以后：
    - 命中接管前缀，就复用这轮会话直接 `audio.commit`
    - 没命中接管前缀，就发 `session.cancel`，把临时缓存收掉
  - 同时补单测，明确覆盖“预热后提交”和“预热后取消”两条时序。
- 这次明确不做什么：
  - 不去改 api-server 的身份识别入口绕过音频缺失。
  - 不把普通对话也强行改成 `always_familyclaw`。
- 验证命令：
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m unittest tests.test_translator tests.test_bridge`
  - `C:\Code\FamilyClaw\apps\open-xiaoai-gateway\.venv\Scripts\python.exe -m py_compile open_xiaoai_gateway\translator.py tests\test_translator.py`

- 现场补充结论：
  - 只靠 `is_vad_begin` 还是不够稳，现场设备这次普通对话很可能没有先给独立的 VAD 开始事件。
  - 后续正式方案不再继续赌“什么时候开始建 session”，而是改成 gateway 本地维护最近 6 秒的 PCM 内存环形缓冲。
  - `native_first` 被唤醒后，等待前缀判断期间先只缓存音频，不立刻往 api-server 发正式 `audio.append`。
  - 一旦最终文本命中接管前缀，gateway 会：
    - 先发 `session.start`
    - 再把内存里回溯到的最近音频补发成一串 `audio.append`
    - 最后再发 `audio.commit`
  - 如果最终没有命中接管前缀，就直接清空缓冲，不落盘、不留历史音频。
  - 这样普通对话是否能做声纹识别，不再依赖设备必须先吐出某个理想化的 VAD 事件。

