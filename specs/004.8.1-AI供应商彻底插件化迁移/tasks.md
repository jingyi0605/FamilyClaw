# 任务清单 - AI 供应商彻底插件化迁移

状态：Completed

## 这份任务清单怎么读
只保留两类内容：

- 已完成：已经落地并且需要长期保留的边界
- 防回退：后续任何人再把供应商逻辑塞回核心时，应该先被任务和测试拦住

## 阶段 1：前端契约与品牌资源插件化

- [x] 1.1 给 `ai-provider manifest` 增加 `branding`
  - 结果：Logo、描述文案、深浅色资源由插件声明并由插件目录提供。
- [x] 1.2 给 `ai-provider manifest` 增加 `config_ui`
  - 结果：字段分组、顺序、动作按钮、隐藏规则全部由插件声明。
- [x] 1.3 给 `ai-provider manifest` 增加 `model_discovery`
  - 结果：模型发现由插件声明驱动，不再由核心前端写死 `field.key === 'model_name'`。

## 阶段 2：builtin provider 进入真实插件目录

- [x] 2.1 把 builtin AI provider 全部落成真实插件目录
  - 结果：核心不再生成虚拟 provider 条目。
- [x] 2.2 把品牌资源迁入插件目录
  - 结果：Logo、说明文案只存在于插件目录。
- [x] 2.3 修复 AI 设置页数据源混用
  - 结果：AI 设置页只消费 `/provider-adapters`，不再从 registry 重建 adapter。

## 阶段 3：删除核心前端 fallback

- [x] 3.1 删除核心 Logo/说明文案映射
  - 结果：删除 `AiProviderLogos.tsx` 和核心里的 `adapter_code -> description/logo` 映射。
- [x] 3.2 增加前端回归保护
  - 结果：前端 guard 明确禁止重新引入 provider 品牌硬编码、模型发现特判和 registry 重建 adapter。

## 阶段 4：收紧 manifest 校验

- [x] 4.1 将 `branding / config_ui / model_discovery` 从“支持”收紧为“必须”
  - 结果：插件如果不声明这三类契约，加载阶段直接失败。
- [x] 4.2 增加品牌资源存在性与结构校验
  - 结果：`logo` 和 `description.json` 缺失、损坏或结构非法时直接报错。

## 阶段 5：协议执行层从核心剥离

- [x] 5.1 写死三条边界红线
  - 结果：
  - 核心不得再出现任何供应商协议枚举驱动的请求拼装分支。
  - 任一 provider 的请求编码、流解析、响应提取必须可在插件内独立实现。
  - 新增 provider 如需改核心，只允许改宿主通用能力，不允许改供应商协议逻辑。
- [x] 5.2 设计新的插件 driver 契约
  - 结果：`invoke / ainvoke / stream` 成为统一宿主契约，协议实现移动到插件 SDK 和插件 driver。
- [x] 5.3 拆分 `provider_runtime.py`
  - 结果：核心只保留统一结果对象、错误对象、模板降级和模拟失败逻辑；不再持有 OpenAI / Anthropic / Gemini 协议实现。
- [x] 5.4 将 OpenAI / Anthropic / Gemini 协议迁入插件层
  - 结果：新增 `app/plugins/_sdk/ai_provider_drivers.py` 与 `app/plugins/_sdk/ai_provider_messages.py`，由插件侧复用。
- [x] 5.5 迁移 builtin provider 到插件内 driver
  - 结果：builtin provider manifest 全部改为指向各自插件目录内的 `driver.build_driver`。
- [x] 5.6 改造流式调用入口
  - 结果：`family_qa` 与 `llm_task` 不再直接调用核心协议 runtime，而是先解析 provider driver，再走 `driver.stream`。

## 阶段 6：文档与防回归

- [x] 6.1 更新插件开发文档
  - 结果：文档明确说明哪些能力属于宿主，哪些协议逻辑必须留在插件。
- [x] 6.2 更新 `004.8.1` task 回写
  - 结果：任务状态与实际代码一致。
- [x] 6.3 增加后端边界回归测试
  - 结果：测试明确禁止核心重新出现协议 builder、协议分支和 manifest 指回核心 builder。

## 剩余长期要求

- [x] 新增 provider 时，如果需要特殊 messages、特殊 header、特殊 stream/event、特殊响应提取，只允许改插件或插件 SDK。
- [x] 核心目录下不得再新增 provider 协议枚举分支。
- [x] 前端不得再新增 `adapter_code -> logo/description` 之类的硬编码表。
