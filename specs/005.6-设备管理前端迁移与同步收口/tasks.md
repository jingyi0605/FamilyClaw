# 任务清单 - 设备管理前端迁移与同步收口

状态：IN_PROGRESS

## 这份文档是干什么的

这份任务清单就是拿来防止这次改造又变成老毛病：

- 设置页删了一半，设备页还没接住
- 家庭页加了个标签，但控制能力又接不完整
- 同步筛选说要做，最后只剩一个勾选框

这次的完成标准很直接：

- 设置页只管插件同步
- 家庭页真正接住设备管理
- 全量同步不再一键误触
- 部分同步不再靠肉眼翻列表

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每做完一个任务，必须立刻回写这里
- 这次如果发现某项会碰后端设备同步执行逻辑或设备控制执行逻辑，必须先停下来重新确认边界

---

## 阶段 1：把边界和数据来源先钉死

- [x] 1.1 盘清设置页、家庭页、设备接口的现状边界
  - 状态：DONE
  - 这一步到底做什么：把当前设置页里哪些是插件级能力、哪些是设备级能力，家庭页现在有哪些设备数据，后端已经有哪些现成接口，全部写清楚。
  - 做完你能看到什么：大家知道这次到底是在搬入口，不是在重写后端。
  - 先依赖什么：无
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md) 需求 1、需求 2、需求 3
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [LegacyFamilyPage.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/family/LegacyFamilyPage.tsx)
    - [devices.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/devices.py)
    - [device_actions.py](/C:/Code/FamilyClaw/apps/api-server/app/api/v1/endpoints/device_actions.py)
  - 主要改哪里：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
  - 这一步先不做什么：先不开始写具体组件拆分方案。
  - 怎么算完成：
    1. 设置页和家庭页的职责边界说清楚
    2. 复用接口清单说清楚
  - 怎么验证：
    - 已在 `requirements.md` 和 `design.md` 中写清设置页、家庭页、设备接口边界
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2、§3.1、§6.1

- [x] 1.2 补齐 HA 接口与筛选字段分析
  - 状态：DONE
  - 这一步到底做什么：明确名称、HA 房间、集成分类这三个筛选条件分别来自 HA 哪些接口和哪些字段。
  - 做完你能看到什么：后面设计筛选逻辑时不会再拍脑袋造字段。
  - 先依赖什么：1.1
  - 开始前先看：
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §6、§7
    - [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
    - [connector.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/connector.py)
  - 主要改哪里：
    - [20260317-Home Assistant接口与筛选字段分析.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/docs/20260317-Home%20Assistant接口与筛选字段分析.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
  - 这一步先不做什么：先不决定最终 UI 长什么样。
  - 怎么算完成：
    1. 三个筛选项都有明确数据来源
    2. 写清楚有没有字段缺口以及降级方案
  - 怎么验证：
    - 已新增 [20260317-Home Assistant接口与筛选字段分析.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/docs/20260317-Home%20Assistant接口与筛选字段分析.md)
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` §6.2、§6.3、§7

### 阶段检查

- [x] 1.3 确认这次不碰后端执行逻辑
  - 状态：DONE
  - 这一步到底做什么：在开始实现前再次检查方案，确保没有偷偷滑向“顺手改一下后端同步逻辑”。
  - 做完你能看到什么：边界稳定，可以放心进入实现阶段。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
    - [20260317-Home Assistant接口与筛选字段分析.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/docs/20260317-Home%20Assistant接口与筛选字段分析.md)
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不追加新需求。
  - 怎么算完成：
    1. 需要复用的后端链路和禁止改动的链路都写清楚
    2. 如果存在最小只读字段补充，也明确不属于同步执行逻辑改造
  - 怎么验证：
    - `requirements.md`、`design.md` 已明确“不改后端设备同步执行逻辑、不改设备控制执行逻辑”
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` §1.3、§6.2、§7.3、§10.2

---

## 阶段 2：先把家庭页设备标签接住

- [ ] 2.1 在家庭页新增设备标签与筛选器
  - 状态：TODO
  - 这一步到底做什么：在家庭页的“房间”和“人员”之间插入设备标签，并把房间、设备类型、状态筛选器做出来。
  - 做完你能看到什么：家庭页第一次成为设备列表入口，而不是只在房间卡片里看设备数量。
  - 先依赖什么：1.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md) 需求 2
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §3.3.4、§4.2、§5.1
    - [LegacyFamilyPage.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/family/LegacyFamilyPage.tsx)
    - [create-api-client.ts](/C:/Code/FamilyClaw/packages/user-core/src/api/create-api-client.ts)
  - 主要改哪里：
    - [LegacyFamilyPage.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/family/LegacyFamilyPage.tsx)
    - [create-api-client.ts](/C:/Code/FamilyClaw/packages/user-core/src/api/create-api-client.ts)
    - 家庭页相关样式与 i18n 文件
  - 这一步先不做什么：先不搬设备详情操作能力。
  - 怎么算完成：
    1. 家庭页标签顺序正确
    2. 设备列表支持三类筛选
  - 怎么验证：
    - 人工走查
    - 前端页面测试
  - 对应需求：`requirements.md` 需求 2
  - 对应设计：`design.md` §4.2、§6.1.3、§8.1

- [ ] 2.2 抽离共享设备详情与操作组件
  - 状态：TODO
  - 这一步到底做什么：把现在设置页里那坨设备详情、实体控制、日志逻辑拆成家庭页能复用的共享组件。
  - 做完你能看到什么：设备详情能力不再绑死在设置页里。
  - 先依赖什么：2.1
  - 开始前先看：
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §4.3
    - [IntegrationDevicePanel.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/IntegrationDevicePanel.tsx)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
  - 主要改哪里：
    - 新的共享设备组件目录
    - [LegacyFamilyPage.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/family/LegacyFamilyPage.tsx)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
  - 这一步先不做什么：先不处理设置页同步确认逻辑。
  - 怎么算完成：
    1. 家庭页能打开设备详情
    2. 实体控制、收藏、停用、删除、日志都走现有接口
  - 怎么验证：
    - 前端页面测试
    - 相关组件测试
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.2、§3.3.4、§4.3、§6.1.4

### 阶段检查

- [ ] 2.3 确认家庭页已经完整接住设备管理
  - 状态：TODO
  - 这一步到底做什么：检查家庭页是不是已经具备替代设置页设备操作入口的条件。
  - 做完你能看到什么：后面删设置页操作入口时不会掉地上。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
  - 主要改哪里：家庭页相关实现文件
  - 这一步先不做什么：不开始删设置页逻辑，先确认家庭页站稳。
  - 怎么算完成：
    1. 家庭页设备列表可筛选
    2. 设备详情可操作
    3. 关键错误路径可提示
  - 怎么验证：
    - 人工回归
    - 前端测试
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §3.3.4、§8.2、§10.1

---

## 阶段 3：把设置页砍回插件同步中心

- [ ] 3.1 移除设置页设备操作入口，改成只读预览
  - 状态：TODO
  - 这一步到底做什么：把设置页里的设备控制、停用、删除、日志入口拿掉，只保留已同步设备的只读预览。
  - 做完你能看到什么：设置页终于只管插件同步，不再一页两套职责。
  - 先依赖什么：2.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md) 需求 1、需求 3
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §3.3.1、§4.1、§8.2
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 主要改哪里：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - 设置页相关 i18n 与样式文件
  - 这一步先不做什么：先不补同步确认和候选筛选。
  - 怎么算完成：
    1. 设置页没有设备操作按钮
    2. 点击插件实例能打开已同步设备只读预览
  - 怎么验证：
    - 前端页面测试
    - 人工回归
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` §4.1、§10.1

- [ ] 3.2 补全量同步多次确认流程
  - 状态：TODO
  - 这一步到底做什么：把全量同步改成多次确认，不允许一键直冲后端。
  - 做完你能看到什么：用户必须明确知道自己在同步整套设备。
  - 先依赖什么：3.1
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md) 需求 4
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §3.3.2、§9.3
  - 主要改哪里：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 这一步先不做什么：不改后端同步执行 payload。
  - 怎么算完成：
    1. 全量同步前至少经过两层确认
    2. 未完成确认不会发请求
  - 怎么验证：
    - 前端交互测试
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §3.3.2、§10.2

- [ ] 3.3 补部分同步的搜索与筛选
  - 状态：TODO
  - 这一步到底做什么：把候选设备弹层从“勾选列表”升级成可搜索、可按 HA 房间和集成分类筛选的选择器。
  - 做完你能看到什么：候选设备多的时候还能快速找到要同步的那几个。
  - 先依赖什么：3.1
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md) 需求 5、需求 6
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md) §3.3.3、§5.2、§5.3、§6.2、§6.3
    - [20260317-Home Assistant接口与筛选字段分析.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/docs/20260317-Home%20Assistant接口与筛选字段分析.md)
  - 主要改哪里：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
    - 如确有必要，最小只读候选 DTO 扩展
  - 这一步先不做什么：不改真正的同步执行逻辑。
  - 怎么算完成：
    1. 支持名称搜索
    2. 支持 HA 房间筛选
    3. 支持集成分类筛选或明确降级
    4. 已选状态不会乱丢
  - 怎么验证：
    - 前端页面测试
    - 候选筛选函数测试
  - 对应需求：`requirements.md` 需求 5、需求 6
  - 对应设计：`design.md` §5.2、§5.3、§6.2、§6.3、§7.2

### 阶段检查

- [ ] 3.4 确认设置页已经只剩插件同步职责
  - 状态：TODO
  - 这一步到底做什么：最终检查设置页是不是彻底收口，没再偷偷留设备操作入口。
  - 做完你能看到什么：页面职责终于干净了。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
  - 主要改哪里：设置页相关实现文件
  - 这一步先不做什么：不再加新设备功能。
  - 怎么算完成：
    1. 设置页只剩同步与只读预览
    2. 全量同步和部分同步体验都达标
  - 怎么验证：
    - 人工回归
  - 对应需求：`requirements.md` 需求 1、需求 4、需求 5
  - 对应设计：`design.md` §4.1、§10.1、§10.2

---

## 阶段 4：验收与回写

- [ ] 4.1 完成回归验证清单
  - 状态：TODO
  - 这一步到底做什么：把家庭页、设置页、同步筛选、设备操作这些主链路逐项验一遍。
  - 做完你能看到什么：这次改造不是“看着像完成”，而是真的跑通了。
  - 先依赖什么：3.4
  - 开始前先看：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/design.md)
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/tasks.md)
  - 主要改哪里：
    - 测试文件
    - 如有需要，补充 `docs/` 下的验收记录
  - 这一步先不做什么：不扩大范围。
  - 怎么算完成：
    1. 家庭页设备标签主链路通过
    2. 设置页同步主链路通过
    3. 关键错误场景有反馈
  - 怎么验证：
    - 前端测试
    - 人工回归
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §11

- [ ] 4.2 回写 Spec 真实进度
  - 状态：TODO
  - 这一步到底做什么：随着实现推进，把这份任务文档持续更新，不准假装完成。
  - 做完你能看到什么：别人接手时一眼知道做到哪了。
  - 先依赖什么：全流程推进
  - 开始前先看：
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/tasks.md)
  - 主要改哪里：
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.6-设备管理前端迁移与同步收口/tasks.md)
  - 这一步先不做什么：不把没做完的事情写成 `DONE`。
  - 怎么算完成：
    1. 每个任务状态真实
    2. 阻塞和取消项写明原因
  - 怎么验证：
    - 人工核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
