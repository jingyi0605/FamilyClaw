# 任务清单 - 小爱音箱全插件化迁移
状态：TODO

## 这份任务清单是干什么的

这次最容易翻车的地方不是不会写代码，而是写着写着又滑回“小爱先单独特判一下，以后再说”。

这份任务清单的作用只有一个：

- 强迫我们先把正式主链搭起来
- 再把旧小爱特例迁进去
- 最后把旧代码删掉

如果最后只是“新代码加了一套，旧代码也还活着”，那这次改造就算失败。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：代码有了，正在复核
- `DONE`：已经完成并回写
- `CANCELLED`：明确不做，并写清原因

规则：

- 只有 `状态：DONE` 的任务才能改成 `[x]`
- 只标真实完成的项，不许提前打勾
- 如果因为兼容原因临时保留旧代码，必须在对应任务里写清退出条件

---

## 阶段 1：先把现状和边界钉死

- [ ] 1.1 盘清当前小爱旧链路和正式插件主链的断点
  - 状态：TODO
  - 这一步做什么：把现有小爱 discovery、claim、binding、control、前端入口逐个盘出来，明确哪些属于旧特例，哪些已经在正式主链里可复用
  - 做完以后能看到什么结果：后面改造时不会再把旧逻辑误当成正式能力继续复用
  - 依赖什么：无
  - 主要改哪些文件：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/design.md)
  - 这一步明确不做什么：先不写实现代码
  - 怎么验证：
    - `design.md` 写清当前旧链路入口、正式主链入口、关键断点

- [ ] 1.2 确认平台保留能力与插件下沉边界
  - 状态：TODO
  - 这一步做什么：明确哪些能力继续保留在平台，例如 `speaker` 动作协议、设备页、声纹管理；哪些能力必须由小爱插件适配
  - 做完以后能看到什么结果：后面不会把声纹或设备协议碎片化到插件里
  - 依赖什么：1.1
  - 主要改哪些文件：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/design.md)
  - 这一步明确不做什么：先不讨论 UI 细节
  - 怎么验证：
    - `requirements.md` 和 `design.md` 明确写出平台职责与插件职责

### 阶段检查

- [ ] 1.3 确认这次不允许保留“小爱主链例外”
  - 状态：TODO
  - 这一步做什么：把“所有操作必须走标准插件控制链路”写成明确边界，并列出迁移完成后必须删除的旧代码类型
  - 做完以后能看到什么结果：后续实现不再能用“先兼容一下”偷渡成长期方案
  - 依赖什么：1.2
  - 主要改哪些文件：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/design.md)
  - 这一步明确不做什么：先不删代码，先写清删除范围
  - 怎么验证：
    - `requirements.md` 有明确“迁移完成后必须删除旧小爱代码”的要求

---

## 阶段 2：把实例和插件选择逻辑泛化

- [ ] 2.1 去掉集成实例与插件选择中的硬编码白名单
  - 状态：TODO
  - 这一步做什么：把当前只认 HA 的集成插件判断、sync scope 判断、实例动作能力判断改成基于注册插件与 manifest 能力
  - 做完以后能看到什么结果：小爱和后续其他设备插件都能进入同一套实例主链
  - 依赖什么：1.3
  - 主要改哪些文件：
    - `apps/api-server/app/modules/integration/service.py`
    - `apps/api-server/app/modules/integration/schemas.py`
    - 相关测试文件
  - 这一步明确不做什么：先不接小爱 discovery 数据源
  - 怎么验证：
    - 新插件不改硬编码白名单也能出现在集成目录
    - 相关测试覆盖通过

- [ ] 2.2 新增正式小爱内置插件骨架
  - 状态：TODO
  - 这一步做什么：创建正式 `manifest + connector + executor`，让小爱以正规内置插件身份被注册
  - 做完以后能看到什么结果：平台插件注册表里有正式小爱插件，而不是只有旧模块
  - 依赖什么：2.1
  - 主要改哪些文件：
    - `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/manifest.json`
    - `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/connector.py`
    - `apps/api-server/app/plugins/builtin/open_xiaoai_speaker/executor.py`
    - 相关 runtime/adapter 文件
  - 这一步明确不做什么：先不切前端入口
  - 怎么验证：
    - 插件注册表和集成目录能看到该插件

### 阶段检查

- [ ] 2.3 确认小爱已经能作为正式实例被创建
  - 状态：TODO
  - 这一步做什么：补齐配置表单、实例创建、实例读取链路，确保不是只有插件注册成功
  - 做完以后能看到什么结果：用户可以创建正式“小爱音箱实例”
  - 依赖什么：2.2
  - 主要改哪些文件：
    - 小爱插件 manifest
    - `apps/api-server/app/modules/integration/service.py`
    - 相关测试
  - 这一步明确不做什么：先不认领设备
  - 怎么验证：
    - 能创建实例并在实例列表里看到

---

## 阶段 3：把发现和设备添加迁到正式主链

- [ ] 3.1 设计并落地通用 discovery 数据源
  - 状态：TODO
  - 这一步做什么：为插件发现结果提供正式持久化承载，优先复用现有模型；如果没有合适模型，就新增通用 discovery 表并走 Alembic
  - 做完以后能看到什么结果：小爱待添加音箱不再只活在内存里
  - 依赖什么：2.3
  - 主要改哪些文件：
    - 对应 model
    - Alembic migration
    - discovery service / repository
    - 相关测试
  - 这一步明确不做什么：先不删旧 discovery 接口
  - 怎么验证：
    - 数据库 migration 能升级
    - PostgreSQL upgrade 验证通过
    - discovery 数据能被正式读回

- [ ] 3.2 把网关 discovery 上报改接到正式 discovery 数据源
  - 状态：TODO
  - 这一步做什么：让 open-xiaoai-gateway 的发现上报进入正式 discovery 承载，而不是继续直接驱动旧 claim 主链
  - 做完以后能看到什么结果：网关继续能上报发现，但背后的主链已经换成正式插件数据源
  - 依赖什么：3.1
  - 主要改哪些文件：
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
    - `apps/api-server/app/api/v1/endpoints/...`
    - discovery 相关服务
    - 相关测试
  - 这一步明确不做什么：先不切设备控制
  - 怎么验证：
    - discovery 上报后，实例候选列表能读到候选音箱

- [ ] 3.3 让小爱插件 connector 提供候选设备与正式绑定结果
  - 状态：TODO
  - 这一步做什么：通过 connector 输出统一候选设备，支持选中候选设备后创建设备与正式 binding
  - 做完以后能看到什么结果：小爱音箱和 HA 一样，能在实例里“发现候选 -> 添加设备”
  - 依赖什么：3.2
  - 主要改哪些文件：
    - 小爱插件 connector
    - `apps/api-server/app/modules/device_integration/service.py`
    - `apps/api-server/app/modules/integration/service.py`
    - 相关 schemas 与测试
  - 这一步明确不做什么：先不删旧前端 API
  - 怎么验证：
    - 创建出来的 binding 含 `plugin_id + integration_instance_id`
    - 集成资源列表可见

### 阶段检查

- [ ] 3.4 确认小爱设备已经进入正式资源列表
  - 状态：TODO
  - 这一步做什么：验证小爱设备能和 HA 设备一样出现在统一资源列表与设备页主链里
  - 做完以后能看到什么结果：后面设备控制和设备详情不再需要小爱特例入口
  - 依赖什么：3.3
  - 主要改哪些文件：
    - 集成资源读取相关代码
    - 相关测试
  - 这一步明确不做什么：先不删除旧代码
  - 怎么验证：
    - 统一资源列表、设备详情读取通过

---

## 阶段 4：把设备控制切到正式插件路由

- [ ] 4.1 让小爱设备控制只认正式 `plugin_id` 路由
  - 状态：TODO
  - 这一步做什么：把小爱音箱的设备动作执行挂到正式插件 executor，禁止旧的 `platform=open_xiaoai` 特例继续承担主链职责
  - 做完以后能看到什么结果：小爱控制和其他设备一样走统一控制入口
  - 依赖什么：3.4
  - 主要改哪些文件：
    - 小爱插件 executor
    - `apps/api-server/app/modules/device_control/router.py`
    - `apps/api-server/app/modules/device_control/service.py`
    - 相关测试
  - 这一步明确不做什么：不重做平台 `speaker` 协议
  - 怎么验证：
    - 小爱音箱动作通过统一控制入口执行
    - 操作日志仍然正常落地

- [ ] 4.2 复用平台 speaker 与声纹能力，不复制逻辑
  - 状态：TODO
  - 这一步做什么：确保小爱迁移后继续复用平台现有 speaker 协议、设备详情、语音接管、声纹管理
  - 做完以后能看到什么结果：平台能力不碎，插件能力边界清晰
  - 依赖什么：4.1
  - 主要改哪些文件：
    - 设备服务
    - 声纹相关读取链路
    - 前端设备详情相关组件
    - 相关测试
  - 这一步明确不做什么：不新增新的声纹业务流程
  - 怎么验证：
    - 小爱设备详情里原有语音接管与声纹能力仍可用

### 阶段检查

- [ ] 4.3 确认小爱已经彻底站上标准插件控制链路
  - 状态：TODO
  - 这一步做什么：复核 discovery、binding、control 三条链是否都已经以正式插件为准
  - 做完以后能看到什么结果：可以开始删旧代码，而不是继续两套并行
  - 依赖什么：4.2
  - 主要改哪些文件：
    - `tasks.md`
    - 必要的设计回写
  - 这一步明确不做什么：先不动最终清理提交
  - 怎么验证：
    - grep 与测试证明主链已经不依赖旧入口

---

## 阶段 5：删除旧小爱特例代码并收口

- [ ] 5.1 删除旧 discovery / claim / 前端旧 API 入口
  - 状态：TODO
  - 这一步做什么：移除旧小爱专用 discovery endpoint、claim 逻辑、前端旧 API 和无效入口
  - 做完以后能看到什么结果：仓库里不再有“新链路已经有了，但旧入口还在”的混乱状态
  - 依赖什么：4.3
  - 主要改哪些文件：
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - `apps/api-server/app/modules/voice/discovery_registry.py`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - 相关前端页面与 i18n
  - 这一步明确不做什么：不误删平台 speaker 与声纹公共能力
  - 怎么验证：
    - 关键 grep 查不到旧主链调用

- [ ] 5.2 清理旧注释、文档、兼容残留
  - 状态：TODO
  - 这一步做什么：把会误导后续开发的旧注释、旧文档、旧兼容分支一并清理
  - 做完以后能看到什么结果：后续接手的人只会看到一条正式主链
  - 依赖什么：5.1
  - 主要改哪些文件：
    - 相关 docs
    - 相关注释
    - `tasks.md`
  - 这一步明确不做什么：不把没完成的内容写成 DONE
  - 怎么验证：
    - 搜索“小爱添加主链”时只剩正式插件链路文件

### 阶段检查

- [ ] 5.3 确认旧小爱特例主链已经删除完成
  - 状态：TODO
  - 这一步做什么：做最终 grep 自检和代码复核，确认旧特例没有继续承担主链职责
  - 做完以后能看到什么结果：这次迁移真正收口
  - 依赖什么：5.2
  - 主要改哪些文件：
    - `tasks.md`
  - 这一步明确不做什么：不新增范围
  - 怎么验证：
    - grep
    - 测试
    - 人工复核

---

## 阶段 6：验证与回写

- [ ] 6.1 完成后端与前端关键验证
  - 状态：TODO
  - 这一步做什么：执行类型检查、后端测试、migration 验证和关键 grep 自检
  - 做完以后能看到什么结果：不是“看起来迁完了”，而是真的能证明迁完了
  - 依赖什么：5.3
  - 主要改哪些文件：
    - 测试文件
    - 必要时补充 `docs/` 验证记录
  - 这一步明确不做什么：不启动前后端 dev server
  - 怎么验证：
    - 前端类型检查通过
    - 后端关键测试通过
    - 如有 migration，PostgreSQL upgrade 验证通过
    - 旧小爱主链 grep 不再命中

- [ ] 6.2 回写 Spec 真实进度
  - 状态：TODO
  - 这一步做什么：按真实完成情况更新这份任务清单
  - 做完以后能看到什么结果：别人接手时能知道哪些已经落地，哪些还没做完
  - 依赖什么：全流程推进
  - 主要改哪些文件：
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.7-小爱音箱全插件化迁移/tasks.md)
  - 这一步明确不做什么：不虚报进度
  - 怎么验证：
    - 人工核对任务状态与实际代码一致
