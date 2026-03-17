# 任务清单 - AI供应商官方对齐与 Coding Plan 官方插件扩展（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只干一件事：把这次工作拆成可以按顺序做的几步，避免一上来就乱改供应商配置，最后谁都说不清到底改了什么。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部条件卡住
- `IN_REVIEW`：代码和验证已经有结果，等最后复核
- `DONE`：已经完成，并且任务状态已经回写
- `CANCELLED`：确认不做，并写清楚原因

---

## 阶段 1：把 Spec 和证据材料立起来

- [x] 1.1 建立 `001.5.1` Spec 骨架并写清边界
  - 状态：DONE
  - 这一部到底做什么：创建 `README.md`、`requirements.md`、`design.md`、`tasks.md` 和 `docs/README.md`，把这次要修什么、不修什么写清楚。
  - 做完你能看到什么：后续编码不用再靠口头描述猜范围。
  - 先依赖什么：无
  - 开始前先看：
    - `specs/001.5-AI供应商管理插件化与模型摘要重构/`
    - `specs/004.5-插件能力统一接入与版本治理/`
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
  - 主要改哪里：
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/README.md`
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/requirements.md`
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/design.md`
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/tasks.md`
  - 这一部先不做什么：不改业务代码，不启动服务。
  - 怎么算完成：
    1. Spec 主文档已经建好。
    2. 范围、风险和验收标准已经可读。
  - 怎么验证：
    - 人工检查文档内容
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

- [x] 1.2 收口现有报告和新增 3 家 Coding Plan 的对照资料
  - 状态：DONE
  - 这一部到底做什么：把现有 14 家供应商官方核查报告纳入 `docs/`，再补一份百炼、Kimi、GLM Coding Plan 的官方资料与 OpenClaw 对照。
  - 做完你能看到什么：后面修代码时每个默认值、协议族和端点都有出处。
  - 先依赖什么：1.1
  - 开始前先看：
    - `docs/开发者文档/20260317-AI供应商LLM通讯官方文档核查报告.md`
    - `apps/api-server/data/openclaw-main/`
  - 主要改哪里：
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/docs/README.md`
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/docs/20260317-AI供应商LLM通讯官方文档核查报告.md`
    - `specs/001.5.1-AI供应商官方对齐与Coding Plan官方插件扩展/docs/20260317-Coding Plan供应商官方资料与OpenClaw对照.md`
  - 这一部先不做什么：不扩成更多供应商调研。
  - 怎么算完成：
    1. 现有核查报告已归档到本 spec。
    2. 三家 Coding Plan 的对照资料已补齐。
  - 怎么验证：
    - 人工检查 `docs/` 目录
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` 3.5

### 阶段检查

- [x] 1.3 确认 Spec 能直接指导后续编码
  - 状态：DONE
  - 这一部到底做什么：检查需求、设计、任务和证据材料是不是已经能形成闭环。
  - 做完你能看到什么：后续可以直接按 P0 / P1 顺序进入编码，不需要再重新开题。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一部先不做什么：不新增范围。
  - 怎么算完成：
    1. 任务能够对上需求和设计。
    2. 证据材料已经能支撑实现。
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

---

## 阶段 2：修现有 builtin 供应商和流式能力

- [ ] 2.1 先按报告修掉现有 builtin 供应商的错误默认配置
  - 状态：TODO
  - 这一部到底做什么：优先修 `minimax`、`doubao-coding`、`byteplus`、`byteplus-coding` 的默认地址、协议族和请求端点拼接。
  - 做完你能看到什么：这些供应商的默认配置不再和官方文档打架。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` 2.3.1
    - `docs/20260317-AI供应商LLM通讯官方文档核查报告.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
  - 这一部先不做什么：不把老 provider 批量改成插件。
  - 怎么算完成：
    1. 四家高风险供应商的默认配置和官方资料一致。
    2. 对应回归测试通过。
  - 怎么验证：
    - 后端单元测试
    - 人工核对默认值
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` 2.3.1、3.1

- [ ] 2.2 补齐 `claude` 和 `gemini` 的流式实现
  - 状态：TODO
  - 这一部到底做什么：补上真实流式链路，不再让这两家只有非流式实现。
  - 做完你能看到什么：这两家的流式能力真正可用。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.3.1
    - `docs/20260317-AI供应商LLM通讯官方文档核查报告.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - 相关流式测试文件
  - 这一部先不做什么：不顺手重写所有供应商的流式框架。
  - 怎么算完成：
    1. `claude` 流式可用。
    2. `gemini` 流式可用。
  - 怎么验证：
    - 流式单元测试 / 集成测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` 2.3.1、6.3

### 阶段检查

- [ ] 2.3 确认现有 builtin 供应商修复已经站稳
  - 状态：TODO
  - 这一部到底做什么：把 P0 / P1 修复和流式能力一起做回归，确认没有引入兼容性回退。
  - 做完你能看到什么：旧供应商的主链路稳定，新供应商开发可以继续往前走。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：相关测试和文档
  - 这一部先不做什么：不加 3 家新插件之外的供应商。
  - 怎么算完成：
    1. 报告里的 P0 / P1 已处理。
    2. 流式补齐已验证。
  - 怎么验证：
    - 回归测试
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 6
  - 对应设计：`design.md` 2.3.1、7.1、7.2

---

## 阶段 3：新增 3 家 Coding Plan 官方插件

- [ ] 3.1 创建百炼、Kimi、GLM 三家官方 `ai-provider` 插件 manifest
  - 状态：TODO
  - 这一部到底做什么：按官方插件方式新增 3 个独立 manifest，并写入字段 schema、协议族、默认地址和文案。
  - 做完你能看到什么：系统里出现 3 个可挂载的官方 `ai-provider` 插件。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4
    - `design.md` 3.2、3.3、3.4、3.5
    - `docs/20260317-Coding Plan供应商官方资料与OpenClaw对照.md`
  - 主要改哪里：
    - 官方插件目录下的 3 个 `manifest.json`
    - 相关插件发现 / 测试文件
  - 这一部先不做什么：不把它们写进 builtin provider 注册表。
  - 怎么算完成：
    1. 3 个 manifest schema 校验通过。
    2. adapter 列表里能看到 3 家新插件。
  - 怎么验证：
    - manifest 校验
    - 插件快照和 adapter 测试
  - 对应需求：`requirements.md` 需求 3、需求 4
  - 对应设计：`design.md` 2.3.2、3.2、3.3、3.4、6.1

- [ ] 3.2 打通家庭挂载、创建配置和执行前校验
  - 状态：TODO
  - 这一部到底做什么：让家庭只有在挂载并启用对应官方插件后，才能创建和使用这 3 家供应商配置。
  - 做完你能看到什么：新增供应商真正服从统一插件边界。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 5、需求 6
    - `design.md` 2.3.2、4.1、4.2、5.2
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/service.py`
    - `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
    - 相关集成测试
  - 这一部先不做什么：不改现有旧 provider profile 的存储结构。
  - 怎么算完成：
    1. 未挂载插件时不能创建或运行对应 provider。
    2. 已挂载时能正常创建和执行。
  - 怎么验证：
    - 集成测试
    - 人工验收
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` 2.3.2、4.1、4.2、5.2、6.2

### 阶段检查

- [ ] 3.3 确认新旧两套路径没有互相打架
  - 状态：TODO
  - 这一部到底做什么：检查旧 builtin provider 和新增官方插件 provider 能不能共存，且不会互相覆盖或误判。
  - 做完你能看到什么：新路径能用，旧路径没被打坏。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：相关测试和文档
  - 这一部先不做什么：不再新增第四家 Coding Plan。
  - 怎么算完成：
    1. 新旧 provider 可同时存在。
    2. 插件状态变化能正确影响官方插件 provider。
  - 怎么验证：
    - 回归测试
    - 人工走查
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` 2.3.2、4.1、4.2、6.1、6.2

---

## 阶段 4：测试、验收和收口

- [ ] 4.1 补齐测试和人工验收记录
  - 状态：TODO
  - 这一部到底做什么：把 builtin 修复、流式能力和 3 家新插件的验证证据补完整。
  - 做完你能看到什么：这次改造不是“理论完成”，而是有证据的完成。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 非功能需求 3
    - `design.md` 7.1、7.2、7.3
    - `docs/README.md`
  - 主要改哪里：
    - 测试文件
    - `docs/README.md`
    - 需要补充的验收记录文档
  - 这一部先不做什么：不扩范围做更多供应商。
  - 怎么算完成：
    1. 自动测试覆盖关键链路。
    2. 人工验收步骤和结果可追踪。
  - 怎么验证：
    - 执行测试
    - 人工验收记录
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 7.1、7.2、7.3、7.4

- [ ] 4.2 最终检查并收口 Spec
  - 状态：TODO
  - 这一部到底做什么：确认需求、设计、任务和验证证据已经对上，把这份 Spec 从“计划”收口到“已交付”。
  - 做完你能看到什么：后续接手的人能直接看懂这次到底改了什么、怎么验收、剩什么风险。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一部先不做什么：不追加新需求。
  - 怎么算完成：
    1. 任务状态全部真实回写。
    2. 风险和延期项都写清楚。
  - 怎么验证：
    - 按 Spec 全量走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
