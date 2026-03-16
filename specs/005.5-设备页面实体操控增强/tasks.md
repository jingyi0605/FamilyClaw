# 任务清单 - 设备页面实体操控增强
状态：Draft

## 这份任务清单是干什么的

这份清单不是为了显得流程很正规，而是为了防止这次改造再次变成“后端多了一些能力，但设备页还是不好用”。

这次的完成标准很简单：

- 用户打开设备页后，能先看到常用实体
- 用户能在设备页里真正管理设备
- 用户能查到设备最近被怎么操作过

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已完成实现，正在验证
- `DONE`：已完成并且已经回写这份任务文档
- `CANCELLED`：确认不做，并写清楚原因

规则：

- 只有 `状态：DONE` 的任务才能标记为 `[x]`
- 每做完一步，就回写真实状态，不准把没做完的任务写成完成
- 涉及数据库结构变更时，必须先改 model，再补 Alembic migration，再做升级验证

---

## 阶段 1：把设备页的信息结构定对

- [ ] 1.1 梳理设备页需要展示的设备级动作和实体级动作
  - 状态：TODO
  - 这一步做什么：明确哪些是设备级动作，哪些是实体级动作，避免页面结构再次混乱
  - 做完以后能看到什么：设备页头部和实体列表的职责清楚，不会把删除、停用、控制、收藏全堆在一起
  - 依赖什么：`005.4` 的设备页和控制链路已经可用
  - 主要改哪些文件：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 这一步明确不做什么：先不写具体 UI 细节和样式实现
  - 怎么验证：
    1. 页面结构图或设计说明能明确区分设备级与实体级动作
    2. 没有“删除实体其实删设备”这种歧义

- [ ] 1.2 明确设备页默认进入“收藏的实体”标签
  - 状态：TODO
  - 这一步做什么：把设备页默认视图定成 `收藏的实体`，并定义无收藏时的空状态
  - 做完以后能看到什么：进入设备页后第一屏不再是全量实体堆叠
  - 依赖什么：1.1
  - 主要改哪些文件：
    - [requirements.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/requirements.md)
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
  - 这一步明确不做什么：先不实现复杂筛选
  - 怎么验证：
    1. 默认标签规则写清楚
    2. 无收藏时的空状态文案和跳转行为写清楚

---

## 阶段 2：补实体收藏与双标签视图

- [ ] 2.1 设计实体收藏的数据结构和接口
  - 状态：TODO
  - 这一步做什么：确定实体收藏是持久化能力，不是前端临时状态
  - 做完以后能看到什么：收藏关系有清楚的数据归属和接口边界
  - 依赖什么：1.2
  - 主要改哪些文件：
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
    - 后续实现预计会改动 `apps/api-server/app/modules/device/` 相关模型和接口
  - 这一步明确不做什么：先不设计批量收藏
  - 怎么验证：
    1. 明确收藏关系表或等价模型
    2. 明确收藏/取消收藏接口，而不是整包覆盖

- [ ] 2.2 实现设备页“收藏的实体 / 全部实体”双标签视图
  - 状态：TODO
  - 这一步做什么：把设备页改成两个标签页，并把默认视图切到收藏实体
  - 做完以后能看到什么：设备页打开后先看常用实体，需要时再切到全部实体
  - 依赖什么：2.1
  - 主要改哪些文件：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
  - 这一步明确不做什么：先不做额外高级筛选器
  - 怎么验证：
    1. 默认显示 `收藏的实体`
    2. 能切换到 `全部实体`
    3. 收藏和取消收藏后两个标签页内容正确更新

---

## 阶段 3：把设备管理动作补完整

- [ ] 3.1 设计并实现停用设备能力
  - 状态：TODO
  - 这一步做什么：新增设备停用动作，并定义停用后的行为
  - 做完以后能看到什么：用户可以先停用设备，而不是只能删除
  - 依赖什么：2.2
  - 主要改哪些文件：
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
    - 后续实现预计会改动 `apps/api-server/app/modules/device/`
    - 后续实现预计会改动 [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 这一步明确不做什么：先不做批量停用
  - 怎么验证：
    1. 停用后设备状态清楚可见
    2. 停用状态下不能继续执行控制

- [ ] 3.2 设计并实现删除设备能力
  - 状态：TODO
  - 这一步做什么：新增删除设备入口，并明确删除后的跳转和数据清理策略
  - 做完以后能看到什么：用户可以在设备页删除无用设备，不再依赖额外脚本或后台处理
  - 依赖什么：3.1
  - 主要改哪些文件：
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
    - 后续实现预计会改动 `apps/api-server/app/modules/device/`
    - 后续实现预计会改动 [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
  - 这一步明确不做什么：先不做回收站或恢复功能
  - 怎么验证：
    1. 删除前有明确确认
    2. 删除后会离开当前详情页
    3. 收藏、绑定、记录的处理策略有明确定义

---

## 阶段 4：把设备操作记录补上

- [ ] 4.1 设计统一设备操作记录模型和查询接口
  - 状态：TODO
  - 这一步做什么：定义设备控制历史怎么存、怎么查、展示哪些字段
  - 做完以后能看到什么：设备页的操作记录不再依赖插件自带日志
  - 依赖什么：3.2
  - 主要改哪些文件：
    - [design.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/design.md)
    - 后续实现预计会改动 `apps/api-server/app/modules/device/` 或统一控制链路模块
  - 这一步明确不做什么：先不做全局审计中心
  - 怎么验证：
    1. 记录模型字段足够支撑设备页展示
    2. 查询接口支持按设备读取最近记录

- [ ] 4.2 在设备页接入操作记录查看入口
  - 状态：TODO
  - 这一步做什么：把操作记录查看能力接进设备页面
  - 做完以后能看到什么：用户可以直接在设备页查看最近操作历史
  - 依赖什么：4.1
  - 主要改哪些文件：
    - [index.tsx](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/integrations/index.tsx)
    - [settingsApi.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsApi.ts)
    - [settingsTypes.ts](/C:/Code/FamilyClaw/apps/user-app/src/pages/settings/settingsTypes.ts)
  - 这一步明确不做什么：先不做复杂筛选和导出
  - 怎么验证：
    1. 设备页能打开操作记录
    2. 记录里至少有时间、动作、实体、结果
    3. 无记录时有明确空状态

---

## 阶段 5：回归验证与收口

- [ ] 5.1 完成前后端验收清单
  - 状态：TODO
  - 这一步做什么：把页面、接口、数据和迁移验证串起来，避免功能看着有、实际上不可用
  - 做完以后能看到什么：这次改造有一套可执行的完成标准，而不是停在描述层
  - 依赖什么：4.2
  - 主要改哪些文件：
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/tasks.md)
    - 后续实现相关测试文件
  - 这一步明确不做什么：不扩大到新的插件接入需求
  - 怎么验证：
    1. 默认收藏实体视图可用
    2. 删除和停用可用
    3. 操作记录可用
    4. 类型检查、后端编译检查和必要测试项明确

- [ ] 5.2 回写 Spec 真实进度
  - 状态：TODO
  - 这一步做什么：随着后续实现推进，持续回写任务状态
  - 做完以后能看到什么：别人接手时能一眼看出哪些做完了，哪些还没做
  - 依赖什么：全流程推进
  - 主要改哪些文件：
    - [tasks.md](/C:/Code/FamilyClaw/specs/005.5-设备页面实体操控增强/tasks.md)
  - 这一步明确不做什么：不允许把没完成的任务标成 `DONE`
  - 怎么验证：
    1. 每个完成项都有真实状态
    2. 没做完的内容保持 `TODO` 或 `IN_PROGRESS`
