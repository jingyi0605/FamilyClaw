# 任务清单 - HA 彻底插件化收尾（人话版）

状态：Draft

## 这份文档是干什么的

这不是又一份“改造愿景清单”，而是一份收尾作战单。

它要解决的问题很直接：

- 哪些残留还在
- 谁来清
- 清到什么程度才算完
- 哪些证据不齐就不准说 DONE

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 没有 grep 结果、白名单说明、测试结果和剩余残留清单，不准进 `DONE`
- `005.4` 的任务状态如果和代码不一致，先回写 spec，再继续做
- 不允许用“基本完成”“已经差不多了”代替任务状态

---

## 阶段 1：先把主口径、基线和禁区钉死

- [x] 1.1 创建 `004.8.4` 收尾主 spec
  - 状态：DONE
  - 这一步到底做什么：把这次收尾的目标、禁区、验收规则和作战顺序单独固化出来，不再把 `005.1`、`005.4`、`005.6` 混着说。
  - 做完你能看到什么：以后再讨论“HA 有没有彻底插件化”，先看这份 spec，而不是凭口头描述。
  - 先依赖什么：无
  - 开始前先看：
    - `specs/000-Spec规范/Codex-Spec规范文档.md`
    - `specs/005.1-设备控制与家居接入插件化改造/requirements.md`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
    - `specs/005.6-设备管理前端迁移与同步收口/requirements.md`
  - 主要改哪里：
    - `specs/004.8.4-HA彻底插件化收尾/README.md`
    - `specs/004.8.4-HA彻底插件化收尾/requirements.md`
    - `specs/004.8.4-HA彻底插件化收尾/design.md`
    - `specs/004.8.4-HA彻底插件化收尾/tasks.md`
    - `specs/004.8.4-HA彻底插件化收尾/docs/`
  - 这一步先不做什么：先不改业务代码，只冻结规则和入口。
  - 怎么算完成：
    1. 已明确 `005.1`、`005.4`、`005.6` 和 `004.8.4` 的主从关系
    2. 已把“没有证据不准说完成”写成规则
  - 怎么验证：
    - 人工走查当前 spec 全文
  - 对应需求：`requirements.md` 需求 1、需求 6、需求 7
  - 对应设计：`design.md` §2.1、§3.3.2、§6.3

- [ ] 1.2 产出当前 HA 残留基线和白名单初稿
  - 状态：TODO
  - 这一步到底做什么：把当前仓库里已知的核心越界、插件越界、前端越界和旧路径遗留全部列出来，并明确哪些是必须立刻删、哪些可以短期白名单。
  - 做完你能看到什么：不再有人说“我以为已经清零了”，每个残留都有编号和归属。
  - 先依赖什么：1.1
  - 开始前先看：
    - `docs/20260319-HA彻底插件化边界验收口径.md`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
    - 当前已知残留文件
  - 主要改哪里：
    - `specs/004.8.4-HA彻底插件化收尾/docs/20260319-HA彻底插件化边界验收口径.md`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
  - 这一步先不做什么：先不急着删代码，先把地雷图画出来。
  - 怎么算完成：
    1. 当前残留按 `core / plugin / frontend / migration / spec` 分类完成
    2. 白名单条目包含保留原因和删除条件
  - 怎么验证：
    - 固定 grep 走查
    - 人工复核分类是否完整
  - 对应需求：`requirements.md` 需求 1、需求 5、需求 6、需求 7
  - 对应设计：`design.md` §3.2、§3.3.1、§4.1

### 阶段检查

- [ ] 1.3 阶段检查：确认这次不是再打一场糊涂仗
  - 状态：TODO
  - 这一步到底做什么：检查主 spec、残留基线、白名单和 `005.4` 的任务口径是不是已经对齐。
  - 做完你能看到什么：后续每个实施任务都知道自己到底要清什么，而不是边做边猜。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩新需求。
  - 怎么算完成：
    1. 已知残留、白名单和责任任务已一一对上
    2. `005.4` 没有继续把明显未完成项描述成已收口
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 6、需求 7
  - 对应设计：`design.md` §2.1、§4.1、§4.2

---

## 阶段 2：清掉核心层里还在认识 HA 的逻辑

- [ ] 2.1 清理核心模块中的 HA 专名逻辑和平台特判
  - 状态：TODO
  - 这一步到底做什么：把核心目录里仍然直接写着 `Home Assistant`、`home_assistant`、`platform == "home_assistant"` 之类的逻辑逐项清掉，改成统一协议或统一资源语义。
  - 做完你能看到什么：核心看起来像一个宿主，不再像半个 HA 集成模块。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` §2.2、§3.3.1、§6.1
    - 当前已知残留文件：
      - `apps/api-server/app/modules/device/service.py`
      - `apps/api-server/app/modules/device_control/router.py`
      - `apps/api-server/app/modules/device_integration/service.py`
      - `apps/api-server/app/modules/integration/service.py`
      - `apps/api-server/app/modules/context/schemas.py`
      - `apps/api-server/app/modules/context/service.py`
      - `apps/api-server/app/modules/conversation/orchestrator.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/`
    - `apps/api-server/app/api/`
  - 这一步先不做什么：先不处理插件内部偷读路径，那是下一阶段。
  - 怎么算完成：
    1. 核心目录中的 HA 专名业务逻辑已清零或进入明确白名单
    2. 核心不再直接 import HA 插件 runtime 或 client
  - 怎么验证：
    - 核心目录 grep
    - 配置、同步、控制、状态读取主链回归
  - 对应需求：`requirements.md` 需求 2、需求 5、需求 6
  - 对应设计：`design.md` §2.2、§3.3.1、§5.3、§6.1

- [ ] 2.2 补齐宿主缺失的正式抽象接口
  - 状态：TODO
  - 这一步到底做什么：如果核心过去之所以直连 HA，是因为宿主 contract 不够，那就把缺的通用接口补出来，别再用 if/else 和直连凑合。
  - 做完你能看到什么：核心与插件的边界变成正式能力，不再靠临时洞打通。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` §2.2、§3.1、§3.3.1、§6.1、§6.2
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/plugins/builtin/homeassistant_*/`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - 相关宿主 service / contract / schema
  - 这一步先不做什么：先不急着大改前端。
  - 怎么算完成：
    1. 核心与插件之间的必需交互都有正式 contract
    2. 后续插件不需要再靠核心内部实现才能工作
  - 怎么验证：
    - contract 单元测试
    - 相关主链集成测试
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.1、§3.3.1、§6.1、§6.2

### 阶段检查

- [ ] 2.3 阶段检查：确认核心已经不再偷偷当 HA 宿主业务层
  - 状态：TODO
  - 这一步到底做什么：复核核心目录是否已经只剩统一协议和通用能力，没有继续藏 HA 分支。
  - 做完你能看到什么：后面接平台时不会再沿着旧坏路扩张。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/20260319-HA彻底插件化边界验收口径.md`
  - 主要改哪里：本阶段相关核心文件和文档
  - 这一步先不做什么：不跳过复核直接进插件整改。
  - 怎么算完成：
    1. 核心残留要么已关闭，要么进入受控白名单
    2. 没有新的 HA 特判补丁被带进来
  - 怎么验证：
    - 核心 grep
    - 关键主链回放
  - 对应需求：`requirements.md` 需求 2、需求 5、需求 6
  - 对应设计：`design.md` §2.2、§4.2、§6.1

---

## 阶段 3：把 HA 插件从“特权模块”收成“正式插件”

- [ ] 3.1 清理 HA 插件对核心仓储、密钥和数据库的直连
  - 状态：TODO
  - 这一步到底做什么：删除 HA 插件里对核心 repository、`config_crypto` 和 `database_url` 的直接依赖，把这些需求改成走宿主 contract。
  - 做完你能看到什么：插件终于像插件，不再是拿着宿主钥匙乱开门的特殊模块。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` §3.3.1、§5.3、§6.2
    - 当前已知残留文件：
      - `apps/api-server/app/plugins/builtin/homeassistant_device_action/runtime.py`
      - `apps/api-server/app/plugins/builtin/homeassistant_device_action/adapter.py`
      - `apps/api-server/app/plugins/builtin/homeassistant_device_action/integration.py`
  - 主要改哪里：
    - `apps/api-server/app/plugins/builtin/homeassistant_*/`
    - 宿主提供的相关 contract
  - 这一步先不做什么：先不碰产品页面表现。
  - 怎么算完成：
    1. 插件目录不再直接 import 核心 repository 与 `config_crypto`
    2. 插件目录不再用 `database_url` 自建会话偷读核心表
  - 怎么验证：
    - 插件目录 grep
    - 配置读取、设备同步、房间同步、状态加载回归
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` §3.3.1、§5.3、§6.2

- [ ] 3.2 收口 HA 配置、同步和状态读取 contract
  - 状态：TODO
  - 这一步到底做什么：把配置读取 scope、实例读取、同步入口和状态读取统一到正式实例级 contract，彻底消灭“表单说配置完成、runtime 却认不到”的双口径。
  - 做完你能看到什么：配置、同步和状态读取走的是同一套正式数据语义，不再各写一套猜法。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` §2.2、§3.2、§3.3.1、§6.2
    - 当前直接问题相关文件：
      - `apps/api-server/app/modules/plugin/config_service.py`
      - `apps/api-server/app/modules/plugin/repository.py`
      - `apps/api-server/app/plugins/builtin/homeassistant_device_action/runtime.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/plugins/builtin/homeassistant_*/`
  - 这一步先不做什么：先不做新功能扩展。
  - 怎么算完成：
    1. 保存配置、读取配置、执行同步和读取状态都使用同一实例级语义
    2. 不再出现 scope 错配和旧桥接逻辑兜底
  - 怎么验证：
    - HA 新建实例配置回归
    - HA 点击同步回归
    - 设备状态加载回归
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` §2.2、§3.2、§3.3.1、§6.2

### 阶段检查

- [ ] 3.3 阶段检查：确认 HA 插件已经失去特权通道
  - 状态：TODO
  - 这一步到底做什么：复核 HA 插件是否已经只能通过宿主 contract 工作，不再保留偷读实现的后门。
  - 做完你能看到什么：这时再说“HA 是插件”，才不是假的。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/20260319-HA彻底插件化边界验收口径.md`
  - 主要改哪里：本阶段相关插件文件和文档
  - 这一步先不做什么：不跳过复核直接宣布插件化完成。
  - 怎么算完成：
    1. 插件越界调用已清零或明确登记白名单
    2. 关键链路回归通过
  - 怎么验证：
    - 插件目录 grep
    - 关键配置与同步回归
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` §3.3.1、§4.2、§6.2

---

## 阶段 4：清掉前端、文档和旧 spec 里的假收口

- [ ] 4.1 清理前端顶层 HA 特例文案、类型和流程
  - 状态：TODO
  - 这一步到底做什么：把 `user-app` 里还在顶层写死的 Home Assistant 文案、字段、图标猜测和流程分支清掉，统一收口到插件元数据和资源模型。
  - 做完你能看到什么：前端看见的是插件和资源，不再看见一个被硬编码进产品顶层的 HA。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6
    - `design.md` §2.2、§3.3.1
    - 当前已知残留文件：
      - `apps/user-app/src/pages/settings/index.tsx`
      - `apps/user-app/src/pages/settings/integrations/index.tsx`
      - `apps/user-app/src/runtime/h5-shell/i18n/I18nProvider.tsx`
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/`
    - `apps/user-app/src/runtime/`
  - 这一步先不做什么：不重做整套前端设计。
  - 怎么算完成：
    1. 前端顶层 HA 特例文案、字段和特判分支已清零或进入白名单
    2. 页面只通过统一实例和统一资源语义工作
  - 怎么验证：
    - 前端目录 grep
    - 统一实例与资源链路回归
  - 对应需求：`requirements.md` 需求 4、需求 6
  - 对应设计：`design.md` §2.2、§3.3.1

- [ ] 4.2 回写 `005.1`、`005.4`、`005.6` 和相关文档的真实进度
  - 状态：TODO
  - 这一步到底做什么：把旧 spec 里与现状不符的“当前执行说明”“完成状态”和主从关系回写正确，别再让下一轮开发继续踩假地图。
  - 做完你能看到什么：打开 spec 就能知道真相，不再需要猜“这个 DONE 到底真的假的”。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 7
    - `design.md` §2.1、§4.1、§4.2
    - `specs/005.1-设备控制与家居接入插件化改造/*`
    - `specs/005.4-设备与集成全插件化重构/*`
    - `specs/005.6-设备管理前端迁移与同步收口/*`
  - 主要改哪里：
    - 上述 spec 文档
    - 相关开发文档和 README
  - 这一步先不做什么：不把还没完成的事写成 DONE。
  - 怎么算完成：
    1. 旧 spec 的主从关系已说明清楚
    2. 任务状态与代码现状对齐
    3. 误导性的“已完成”描述已回写
  - 怎么验证：
    - 文档人工走查
    - 抽样对照代码残留
  - 对应需求：`requirements.md` 需求 1、需求 7
  - 对应设计：`design.md` §2.1、§4.1、§4.2

### 阶段检查

- [ ] 4.3 阶段检查：确认产品层和文档层不再帮旧逻辑打掩护
  - 状态：TODO
  - 这一步到底做什么：检查前端顶层和 spec 口径是不是都已经和真实边界对齐。
  - 做完你能看到什么：功能、代码、文档和验收说的是同一件事。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/20260319-HA彻底插件化边界验收口径.md`
  - 主要改哪里：本阶段相关前端和 spec 文件
  - 这一步先不做什么：不跳过检查直接宣布收尾完成。
  - 怎么算完成：
    1. 前端顶层没有继续扩张 HA 特例
    2. 旧 spec 不再误导实现和验收
  - 怎么验证：
    - 前端 grep
    - 文档走查
  - 对应需求：`requirements.md` 需求 4、需求 7
  - 对应设计：`design.md` §2.1、§2.2、§4.2

---

## 阶段 5：拿证据收尾，不再靠口头收尾

- [ ] 5.1 产出最终 grep、白名单和剩余残留证据包
  - 状态：TODO
  - 这一步到底做什么：把固定 grep 结果、白名单、剩余残留和责任归属整理成最终证据包，作为能不能宣布完成的硬门槛。
  - 做完你能看到什么：任何人都能复核“还剩什么，为什么还剩，凭什么算完成”。
  - 先依赖什么：4.3
  - 开始前先看：
    - `requirements.md` 需求 6、需求 7
    - `design.md` §3.2、§3.3.1、§3.3.2
    - `docs/20260319-HA彻底插件化边界验收口径.md`
  - 主要改哪里：
    - `specs/004.8.4-HA彻底插件化收尾/docs/`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
  - 这一步先不做什么：不拿一句“grep 差不多清了”糊弄过去。
  - 怎么算完成：
    1. 固定 grep 结果已归档
    2. 白名单与剩余残留清单已归档
    3. 每个残留都有责任任务或保留原因
  - 怎么验证：
    - 复跑 grep
    - 人工核对白名单
  - 对应需求：`requirements.md` 需求 6、需求 7
  - 对应设计：`design.md` §3.2、§3.3.1、§3.3.2、§6.3

- [ ] 5.2 完成最终回归和迁移校验
  - 状态：TODO
  - 这一步到底做什么：对配置、同步、控制、状态读取、前端入口和迁移链路做最终回归，证明清理不是靠猜。
  - 做完你能看到什么：这次收尾不是“代码看起来干净了”，而是“主链真的没坏”。
  - 先依赖什么：5.1
  - 开始前先看：
    - `requirements.md` 需求 5、需求 6
    - `design.md` §7
    - 相关测试目录与迁移脚本
  - 主要改哪里：
    - `apps/api-server/tests/`
    - `apps/user-app` 相关测试
    - `apps/api-server/migrations/`
  - 这一步先不做什么：不新增与收尾无关的测试范围。
  - 怎么算完成：
    1. 配置、同步、控制和状态读取回归通过
    2. 前端关键入口回归通过
    3. 迁移与兼容校验通过
  - 怎么验证：
    - 执行测试集
    - 人工回放关键场景
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` §7.1、§7.2、§7.3

### 最终检查

- [ ] 5.3 最终检查点：只有证据齐全，才允许说“HA 彻底插件化完成”
  - 状态：TODO
  - 这一步到底做什么：逐项核对这份 spec 的成功定义，看有没有任何一条还在糊弄。
  - 做完你能看到什么：这次收尾真正闭环，不会再出现第四轮“怎么还没收干净”。
  - 先依赖什么：5.1、5.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/20260319-HA彻底插件化边界验收口径.md`
    - `specs/005.4-设备与集成全插件化重构/tasks.md`
  - 主要改哪里：当前 spec 全部文件，以及与其联动的 `005.4` 文档
  - 这一步先不做什么：不再追加新需求。
  - 怎么算完成：
    1. 成功定义中的每一条都能拿证据对上
    2. 不存在未授权残留
    3. 不存在关键任务状态漂移
  - 怎么验证：
    - 按本 spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
