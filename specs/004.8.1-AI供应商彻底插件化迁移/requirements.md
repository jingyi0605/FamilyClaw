# 需求文档 - AI 供应商彻底插件化迁移

状态：Implemented

## 背景

2026-03-18 之前，项目虽然已经有 `ai-provider` 类型，但核心里仍然保留了供应商注册表、厂商特判和虚拟 manifest。

这次迁移完成后，当前正式规则已经变成：

- 供应商声明来自真实 `ai-provider` 插件
- 宿主通过稳定的 provider driver contract 调用插件
- 厂商特例不再写在核心模块里

## 范围

### In Scope

- 固定宿主与 `ai-provider` 插件的最终职责边界
- 提供稳定的 provider driver contract
- 删除核心里的供应商注册表真相源
- 把厂商协议适配、流式输出和特例迁到插件 driver
- 用真实 builtin plugin manifest 替代虚拟 ai-provider 条目
- 更新所有相关 spec 和开发者文档到统一口径

### Out of Scope

- 重做 AI Gateway 的产品策略、计费或路由算法
- 重做插件市场、远程安装或安全沙箱
- 顺手扩展新的宿主能力

## 角色与边界

### 宿主必须保留

- 统一 AI Gateway 入口
- 路由与 fallback
- 权限、审计、密钥管理
- 插件启停与 household 可见性校验
- 统一错误语义、统一调用结果

### `ai-provider` 插件必须负责

- 供应商声明
- 字段 schema
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

### 需求 2：必须有稳定的 provider driver contract

验收标准：

1. WHEN 宿主加载 `ai-provider` 插件 THEN System SHALL 通过 `entrypoints.ai_provider` 解析 provider driver。
2. WHEN 宿主执行供应商调用 THEN System SHALL 只依赖统一 driver 接口，而不是依赖具体厂商分支。
3. WHEN 新增供应商 THEN System SHALL 原则上不再修改 `app/modules/ai_gateway` 的供应商分发表。

### 需求 3：供应商声明和运行逻辑必须迁出核心

验收标准：

1. WHEN 系统列出 AI 供应商 THEN System SHALL 以插件注册表和真实 manifest 为准。
2. WHEN 系统执行非流式或流式调用 THEN System SHALL 通过 provider driver 调用插件逻辑。
3. WHEN 供应商有厂商特例 THEN System SHALL 把特例留在插件 driver，而不是写回宿主核心。
4. WHEN 检查核心目录 THEN System SHALL 不再存在 `provider_adapter_registry.py` 这类供应商注册表真相源。

### 需求 4：迁移完成后不得回退到半插件化

验收标准：

1. WHEN 开发者新增 builtin AI 供应商 THEN System SHALL 新增真实插件目录和 `manifest.json`。
2. WHEN 开发者尝试继续使用虚拟 ai-provider 条目 THEN System SHALL 被视为违规实现。
3. WHEN 代码评审回扫核心目录 THEN System SHALL 不接受新增供应商名、专有 header 或厂商特判重新进入核心。

### 需求 5：文档必须统一到新口径

验收标准：

1. WHEN 开发者阅读 AI 供应商插件化文档 THEN System SHALL 明确 `004.8.1` 是唯一主 spec。
2. WHEN 开发者阅读旧 spec THEN System SHALL 看到“历史背景”定位，而不是把旧实现误认成现状。
3. WHEN 开发者阅读插件开发文档 THEN System SHALL 看到已经落地的现行边界，不再看到“仍在迁移中”的主表述。

## 非功能需求

### 可维护性

1. WHEN 后续接入新供应商 THEN System SHALL 优先通过新增或修改插件完成，而不是修改宿主核心。
2. WHEN 排查 AI 供应商问题 THEN System SHALL 能快速区分宿主边界问题还是插件实现问题。

### 一致性

1. WHEN 任一文档提到 AI 供应商插件化 THEN System SHALL 使用同一套边界描述。
2. WHEN 任一 builtin AI 供应商接入系统 THEN System SHALL 通过同一类真实 manifest 和 provider driver 机制接入。

### 可验证性

1. WHEN 宣称迁移完成 THEN System SHALL 能提供代码回扫、单元测试和编译检查证据。
2. WHEN 回扫核心目录 THEN System SHALL 能证明供应商痕迹只留在插件目录、测试或历史文档里。

## 成功定义

- 宿主与 `ai-provider` 插件边界稳定
- `provider_adapter_registry.py` 已从核心删除
- `provider_runtime.py` 不再承担厂商特判分发表角色
- builtin AI 供应商全部通过真实插件 manifest 暴露
- 厂商特例迁到插件 driver
- 旧 spec 和开发者文档统一指向 `004.8.1`
