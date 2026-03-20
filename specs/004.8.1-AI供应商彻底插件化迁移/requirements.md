# 需求文档 - AI 供应商彻底插件化迁移

状态：In Progress

## 背景

2026-03-18 之前，项目虽然已经有 `ai-provider` 类型，但核心里仍然保留了供应商注册表、厂商特判和虚拟 manifest。

第一阶段迁移完成后，当前正式规则已经变成：

- 供应商声明来自真实 `ai-provider` 插件
- 宿主通过稳定的 provider driver contract 调用插件
- 厂商特例不再写在核心模块里

但仍未完全达标：

- 前端 Logo、说明文案、表单特殊渲染和模型刷新交互仍有核心硬编码
- `ai-provider` manifest 还没有覆盖 branding、config_ui、model_discovery
- `provider_runtime.py` 仍承担协议级执行桥，是否继续保留在宿主需要重新评估并写死边界

## 范围

### In Scope

- 固定宿主与 `ai-provider` 插件的最终职责边界
- 提供稳定的 provider driver contract
- 删除核心里的供应商注册表真相源
- 把厂商协议适配、流式输出和特例迁到插件 driver
- 用真实 builtin plugin manifest 替代虚拟 ai-provider 条目
- 给 `ai-provider` manifest 增加 branding、config_ui、model_discovery 契约
- 把前端品牌资源、说明文案、表单动作和模型发现交互改成插件声明驱动
- 评估并明确协议级 LLM 请求执行到底留在宿主还是继续下沉到插件
- 更新所有相关 spec 和开发者文档到统一口径

### Out of Scope

- 重做 AI Gateway 的产品策略、计费或路由算法
- 重做插件市场、远程安装或安全沙箱
- 顺手扩展新的宿主能力
- 为了图省事继续把 AI 供应商 UI 特例塞回核心

## 角色与边界

### 宿主必须保留

- 统一 AI Gateway 入口
- 路由与 fallback
- 权限、审计、密钥管理
- 插件启停与 household 可见性校验
- 统一错误语义、统一调用结果
- 通用的协议能力抽象与调用收口

### `ai-provider` 插件必须负责

- 供应商声明
- 品牌资源和说明文案资源
- 字段 schema
- 配置 UI 结构
- 配置动作定义
- 模型自动发现声明
- provider driver entrypoint
- 配置校验
- 协议适配
- 流式输出
- 厂商特例
- 最小诊断信息

## 需求

### 需求 1：宿主与插件边界必须固定

验收标准：

1. WHEN 开发者新增或修改 AI 供应商 THEN System SHALL 只在宿主里处理统一网关、路由、权限、审计、密钥和 fallback。
2. WHEN 开发者实现供应商接入 THEN System SHALL 在 `ai-provider` 插件里实现声明、schema、协议适配、流式输出和厂商特例。
3. WHEN 评审代码变更 THEN System SHALL 能明确判断某段逻辑应该留在宿主还是应该迁到插件。
4. WHEN 某段 AI 供应商相关代码或资源只能服务单一供应商 THEN System SHALL 视其为插件侧内容，而不是宿主内容。

### 需求 2：必须有稳定的 provider driver contract

验收标准：

1. WHEN 宿主加载 `ai-provider` 插件 THEN System SHALL 通过 `entrypoints.ai_provider` 解析 provider driver。
2. WHEN 宿主执行供应商调用 THEN System SHALL 只依赖统一 driver 接口，而不是依赖具体厂商分支。
3. WHEN 新增供应商 THEN System SHALL 原则上不再修改 `app/modules/ai_gateway` 的供应商分发表。
4. WHEN 新增供应商品牌资源、表单动作或模型发现规则 THEN System SHALL 通过插件 manifest 和插件资源接入，而不是通过核心前端常量表接入。

### 需求 3：供应商声明和运行逻辑必须迁出核心

验收标准：

1. WHEN 系统列出 AI 供应商 THEN System SHALL 以插件注册表和真实 manifest 为准。
2. WHEN 系统执行非流式或流式调用 THEN System SHALL 通过 provider driver 调用插件逻辑。
3. WHEN 供应商有厂商特例 THEN System SHALL 把特例留在插件 driver，而不是写回宿主核心。
4. WHEN 检查核心目录 THEN System SHALL 不再存在 `provider_adapter_registry.py` 这类供应商注册表真相源。
5. WHEN 检查核心前端目录 THEN System SHALL 不再存在 `adapter_code -> logo`、`adapter_code -> description key`、`field.key === 'model_name'` 这类 AI 供应商特判。

### 需求 4：`ai-provider` manifest 必须覆盖完整前端契约

验收标准：

1. WHEN 系统加载 `ai-provider` manifest THEN System SHALL 能拿到 branding、config_ui、model_discovery 这三类声明。
2. WHEN 插件声明 branding THEN System SHALL 至少支持 logo 资源路径、说明文案资源路径、可选明暗变体。
3. WHEN 插件声明 config_ui THEN System SHALL 至少支持字段分组、字段顺序、隐藏规则、说明文本和动作按钮。
4. WHEN 插件声明 model_discovery THEN System SHALL 至少支持依赖字段、回填字段、节流时间和空结果提示。

### 需求 5：迁移完成后不得回退到半插件化

验收标准：

1. WHEN 开发者新增 builtin AI 供应商 THEN System SHALL 新增真实插件目录和 `manifest.json`。
2. WHEN 开发者尝试继续使用虚拟 ai-provider 条目 THEN System SHALL 被视为违规实现。
3. WHEN 代码评审回扫核心目录 THEN System SHALL 不接受新增供应商名、专有 header 或厂商特判重新进入核心。
4. WHEN 开发者尝试在核心前端新增 AI 供应商 Logo、说明文案、表单专用 UI 或模型发现分支 THEN System SHALL 被视为违规实现。

### 需求 6：协议级请求执行边界必须被明确写死

验收标准：

1. WHEN 审查 `provider_runtime.py` THEN System SHALL 能明确区分“通用协议能力”与“厂商特例”。
2. WHEN 某种请求执行逻辑无法抽象成稳定宿主能力 THEN System SHALL 把它迁到插件侧，而不是继续在宿主里加例外。
3. WHEN 保留协议能力在宿主 THEN System SHALL 不把供应商品牌、资源、表单和模型发现逻辑重新带回宿主。

### 需求 7：文档必须统一到新口径

验收标准：

1. WHEN 开发者阅读 AI 供应商插件化文档 THEN System SHALL 明确 `004.8.1` 是唯一主 spec。
2. WHEN 开发者阅读旧 spec THEN System SHALL 看到“历史背景”定位，而不是把旧实现误认成现状。
3. WHEN 开发者阅读插件开发文档 THEN System SHALL 看到已经落地的现行边界，不再看到“仍在迁移中”的主表述。

## 非功能需求

### 可维护性

1. WHEN 后续接入新供应商 THEN System SHALL 优先通过新增或修改插件完成，而不是修改宿主核心。
2. WHEN 排查 AI 供应商问题 THEN System SHALL 能快速区分宿主边界问题还是插件实现问题。
3. WHEN 前端新增或修改 AI 供应商配置界面 THEN System SHALL 优先修改插件声明或插件资源，而不是核心组件分支。

### 一致性

1. WHEN 任一文档提到 AI 供应商插件化 THEN System SHALL 使用同一套边界描述。
2. WHEN 任一 builtin AI 供应商接入系统 THEN System SHALL 通过同一类真实 manifest 和 provider driver 机制接入。

### 可验证性

1. WHEN 宣称迁移完成 THEN System SHALL 能提供代码回扫、单元测试和编译检查证据。
2. WHEN 回扫核心目录 THEN System SHALL 能证明供应商痕迹只留在插件目录、测试或历史文档里。
3. WHEN 回扫核心前端目录 THEN System SHALL 能证明不存在 AI 供应商 logo/description/form behavior 的硬编码映射表。

## 成功定义

- 宿主与 `ai-provider` 插件边界稳定
- `provider_adapter_registry.py` 已从核心删除
- `provider_runtime.py` 不再承担厂商特判分发表角色
- builtin AI 供应商全部通过真实插件 manifest 暴露
- 厂商特例迁到插件 driver
- `ai-provider` manifest 覆盖 branding、config_ui、model_discovery
- 核心前端不再维护 AI 供应商 logo/description/form behavior 映射
- 旧 spec 和开发者文档统一指向 `004.8.1`
