# 任务清单 - AI 供应商彻底插件化迁移

状态：In Progress

## 这份任务清单怎么用

这份任务文档只保留两类内容：

- 已完成：已经落地并回写的阶段
- 进行中：为了把 AI 供应商和核心彻底分开，接下来必须继续做的阶段

## 阶段 1：前端契约与品牌资源插件化

- [x] 1.1 给 `ai-provider manifest` 增加 `branding`
  - 状态：DONE
  - 做什么：要求每个 provider 插件声明 logo 资源、说明文案资源和可选深浅色资源
  - 做完后能看到什么结果：前端不再通过 `adapter_code -> logo/description` 映射取品牌资源

- [x] 1.2 给 `ai-provider manifest` 增加 `config_ui`
  - 状态：DONE
  - 做什么：要求每个 provider 插件声明字段分组、字段顺序、说明文字、动作按钮和隐藏规则
  - 做完后能看到什么结果：前端只保留通用渲染器

- [x] 1.3 给 `ai-provider manifest` 增加 `model_discovery`
  - 状态：DONE
  - 做什么：要求每个 provider 插件声明依赖字段、目标字段、节流时间和空结果文案
  - 做完后能看到什么结果：前端不再按 `field.key === 'model_name'` 硬编码刷新模型逻辑

## 阶段 2：builtin provider 迁入真实插件目录

- [x] 2.1 把 builtin AI 供应商全部迁成真实插件
  - 状态：DONE
  - 做什么：将 builtin provider 变成真实的 `ai_provider_*` 插件目录和 manifest
  - 做完后能看到什么结果：核心不再生成虚拟 AI provider 条目

- [x] 2.2 把品牌资源迁入插件目录
  - 状态：DONE
  - 做什么：将 Logo、说明文案资源迁入 provider 插件目录
  - 做完后能看到什么结果：品牌资源只存在于插件目录

- [x] 2.3 修复设置页数据源混用
  - 状态：DONE
  - 做什么：删除 AI 设置页从 `PluginRegistryItem.capabilities.ai_provider` 重建 adapter 的逻辑
  - 做完后能看到什么结果：AI 设置页只消费 `/provider-adapters`

## 阶段 3：清掉核心里的供应商映射和前端 fallback

- [x] 3.1 删除核心 Logo/说明文案映射
  - 状态：DONE
  - 做什么：删除 `AiProviderLogos.tsx` 和 `adapter_code -> description key` 映射
  - 做完后能看到什么结果：前端品牌信息全部来自插件契约

- [x] 3.2 增加防回归 guard
  - 状态：DONE
  - 做什么：增加回扫规则，禁止在核心前端重新引入 AI 供应商 Logo、说明文案、模型发现硬编码和 registry 重建 adapter
  - 做完后能看到什么结果：以后再回退会被检查直接挡住

## 阶段 4：收紧 manifest 校验

- [x] 4.1 把 `branding / config_ui / model_discovery` 从“支持”收紧为“必须”
  - 状态：DONE
  - 做什么：更新 schema 和 manifest 校验逻辑，强制要求这三类契约存在
  - 做完后能看到什么结果：以后不能再打着“插件化”名义把 UI 细节留给核心兜底

- [x] 4.2 增加资源存在性和结构校验
  - 状态：DONE
  - 做什么：校验插件里的 logo 与 description 资源是否存在、description 是否是合法 JSON
  - 做完后能看到什么结果：插件资源契约能在加载阶段就报错

## 阶段 5：补文档和回归测试

- [x] 5.1 更新 `004.8.1`
  - 状态：DONE
  - 做什么：把主 spec 收口成现行规则
  - 做完后能看到什么结果：不再把历史实现误当现状

- [x] 5.2 更新插件开发文档
  - 状态：DONE
  - 做什么：补充 `branding / config_ui / model_discovery` 契约
  - 做完后能看到什么结果：插件作者知道前端契约该怎么写

- [x] 5.3 增加回归测试
  - 状态：DONE
  - 做什么：补 manifest 校验、adapter 输出测试和前端 guard
  - 做完后能看到什么结果：核心不容易再回到半插件化状态

## 阶段 6：把协议执行层彻底从核心剥离

- [ ] 6.1 写死协议边界红线
  - 状态：TODO
  - 做什么：把下面三条写成正式规则并补到 spec 与插件开发文档
  - 三条红线：
    - 核心不得再出现任何供应商协议枚举驱动的请求拼装分支
    - 任一 provider 的请求编码、流解析、响应提取必须可在插件内独立实现
    - 新增 provider 如需改核心，只允许改宿主通用能力，不允许改供应商协议逻辑
  - 做完后能看到什么结果：评审新增 provider 时有统一判定标准
  - 主要改哪些文件：
    - `specs/004.8.1-AI供应商彻底插件化迁移/requirements.md`
    - `specs/004.8.1-AI供应商彻底插件化迁移/design.md`
    - `docs/开发者文档/插件开发/zh-CN/05-插件对接方式说明.md`
  - 这一步不做什么：不直接改 runtime 实现
  - 怎么验证：文档中能明确看出这三条已经是正式规则

- [ ] 6.2 设计新的 provider driver 契约
  - 状态：TODO
  - 做什么：定义插件如何独立接管请求编码、流解析和响应提取；同时保留宿主统一返回格式
  - 做完后能看到什么结果：driver 契约不再只是“请求前改参数”
  - 依赖：6.1
  - 主要改哪些文件：
    - `apps/api-server/app/modules/ai_gateway/provider_driver.py`
    - `apps/api-server/app/modules/ai_gateway/schemas.py`
    - `apps/api-server/app/plugins/_ai_provider_runtime_helpers.py`
    - `docs/开发者文档/插件开发/zh-CN/05-插件对接方式说明.md`
  - 这一步不做什么：不直接迁移所有 builtin provider
  - 怎么验证：契约文档和类型定义能支持插件独立实现协议层

- [ ] 6.3 拆分 `provider_runtime.py`
  - 状态：TODO
  - 做什么：把其中的通用 HTTP/SSE/JSON 能力和供应商协议逻辑拆开
  - 做完后能看到什么结果：核心 runtime 只剩通用能力，不再直接拼 OpenAI / Anthropic / Gemini 请求
  - 依赖：6.2
  - 主要改哪些文件：
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
    - 新增宿主通用 runtime helper 文件
  - 这一步不做什么：不保留新的 `api_family -> builder` 过渡层
  - 怎么验证：回扫 `provider_runtime.py` 时看不到供应商协议分支

- [ ] 6.4 把 OpenAI / Anthropic / Gemini 协议实现迁成插件 SDK 或插件内实现
  - 状态：TODO
  - 做什么：把现有三类协议执行迁出核心，改为插件可复用 SDK 或插件内实现
  - 做完后能看到什么结果：新增同类供应商时只需在插件层复用 SDK
  - 依赖：6.3
  - 主要改哪些文件：
    - `apps/api-server/app/plugins/_sdk/*`
    - `apps/api-server/app/plugins/builtin/ai_provider_*/driver.py`
    - 与之对应的测试文件
  - 这一步不做什么：不把 SDK 重新做成核心协议分发表
  - 怎么验证：新增一个同类 provider 时不需要修改核心协议代码

- [ ] 6.5 迁移现有 builtin provider 到新契约
  - 状态：TODO
  - 做什么：把当前仍依赖核心协议执行层的 builtin AI provider 迁到新的 driver 契约
  - 做完后能看到什么结果：builtin provider 也不再借核心协议实现“代发请求”
  - 依赖：6.4
  - 主要改哪些文件：
    - `apps/api-server/app/plugins/builtin/ai_provider_*/driver.py`
    - 对应 manifest 和测试
  - 这一步不做什么：不引入“临时例外 provider”
  - 怎么验证：builtin provider 链路跑通，且核心不含供应商协议分支

- [ ] 6.6 增加协议层防回归测试
  - 状态：TODO
  - 做什么：增加回扫和单测，明确禁止核心再出现 `api_family -> request builder / stream parser / response extractor`
  - 做完后能看到什么结果：以后谁把协议逻辑写回核心，测试会直接失败
  - 依赖：6.3
  - 主要改哪些文件：
    - `apps/api-server/tests/*`
    - 可能新增核心代码回扫测试
  - 这一步不做什么：不只做文字声明，不做代码保护
  - 怎么验证：新增违规分支时测试能稳定失败
