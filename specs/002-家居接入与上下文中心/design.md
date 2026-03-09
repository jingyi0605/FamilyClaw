# 设计文档 - 家居接入与上下文中心

状态：Draft

## 1. 概述

### 1.1 设计目标

本 Spec 要解决的不是“再多接几个设备”，而是把设备、成员、房间和当前状态串成一个能用的上下文层。

首期设计目标有四个：

1. 让设备接入从“静态清单”升级到“可感知、可执行”
2. 让系统有稳定的成员在家快照和房间占用结果
3. 让前端能一次性拉到家庭上下文总览
4. 让管理员有一套能看、能调、能纠偏的管理界面

### 1.2 范围边界

本期优先完成：

- `Home Assistant` 设备同步复用与基础动作执行
- 在家事件接入与成员状态聚合骨架
- 房间占用和活跃成员热缓存
- 家庭上下文总览查询接口
- 管理台家居上下文仪表盘与配置页

本期明确不做：

- 完整多模态识别算法
- 完整规则引擎与复杂场景编排
- 复杂小米生态双向桥接
- 最终版移动端或家庭屏交互

### 1.3 当前阶段交付策略

当前阶段先落一个**前端原型页**，原因很简单：

- 后端上下文能力还没写完，但管理员页面不能一直空着
- 先把要展示什么、要配置什么定下来，后端接口才不会瞎长
- 配置数据首期允许用浏览器本地持久化承接，后续再替换成后端 `context configs` API

这不是偷懒，这是把数据结构先钉死，避免后面前后端一起乱套。

---

## 2. 架构设计

### 2.1 模块拆分

本 Spec 在现有 `api-server` 基础上新增或扩展以下模块：

1. `ha_integration`
   - 复用设备同步能力
   - 增加基础动作执行封装
2. `presence`
   - 写入原始在家事件
   - 提供事件校验
3. `context_engine`
   - 聚合成员在家状态
   - 计算活跃成员与房间占用
4. `context_cache`
   - 将快照写入 `Redis`
   - 负责读取降级逻辑
5. `context_api`
   - 提供上下文总览与配置接口
6. `admin_web_context`
   - 提供仪表盘、成员状态面板、房间热区和配置界面

### 2.2 运行时依赖

- `SQLite`：持久化原始事件、成员快照与配置
- `Redis`：存储当前家庭热缓存
- `Home Assistant`：设备状态、实体同步与动作执行
- `Admin Web`：查看总览、调整配置、做演示与验收

### 2.3 核心数据流

#### §2.3.1 设备同步流

`Admin Web` / 调度任务 → `ha_integration` → `devices` / `device_bindings` → 审计日志

#### §2.3.2 在家事件流

外部适配器 → `presence` → `presence_events` → `context_engine` → `member_presence_state` → `Redis`

#### §2.3.3 上下文总览查询流

`Admin Web` → `context_api` → 读取 `Redis` 热缓存 → 不足部分补查 `SQLite` 和 `devices` → 聚合响应

#### §2.3.4 设备动作执行流

快路径或管理台 → `context_api` / `ha_integration` → 权限校验 → `Home Assistant` 服务调用 → 审计日志

---

## 3. 组件与接口

### 3.1 复用设备同步接口

继续复用：

- `POST /api/v1/devices/sync/ha`

说明：

- 该接口来自 `Spec 001`
- 本 Spec 不重造轮子，只要求同步结果能被上下文页消费
- 前端仪表盘需展示最近同步结果与设备健康概况

### 3.2 在家事件写入接口

建议新增：

- `POST /api/v1/context/presence-events`

#### 输入

```json
{
  "household_id": "uuid",
  "member_id": "uuid 或 null",
  "room_id": "uuid 或 null",
  "source_type": "lock|camera|bluetooth|sensor|voice",
  "source_ref": "door_lock.main",
  "confidence": 0.92,
  "payload": {
    "event": "unlock",
    "summary": "camera matched parent"
  },
  "occurred_at": "2026-03-09T07:30:00Z"
}
```

#### 输出

```json
{
  "event_id": "uuid",
  "accepted": true,
  "snapshot_updated": true
}
```

#### 校验约束

- `household_id` 必填
- `source_type` 必须在支持枚举内
- `confidence` 范围为 `0 ~ 1`
- `member_id`、`room_id` 若存在，必须属于当前家庭
- `occurred_at` 不得明显超出允许时钟偏差

#### 错误返回

- `400`：字段缺失或枚举非法
- `404`：成员或房间不存在
- `409`：事件重复或冲突
- `422`：置信度、时间戳等语义校验失败

### 3.3 家庭上下文总览接口

建议新增：

- `GET /api/v1/context/overview?household_id=<id>`

#### 输出结构

```json
{
  "household_id": "uuid",
  "home_mode": "home",
  "privacy_mode": "balanced",
  "automation_level": "assisted",
  "home_assistant_status": "healthy",
  "active_member": {
    "member_id": "uuid",
    "name": "Jamie",
    "confidence": 0.91,
    "current_room_id": "uuid"
  },
  "member_states": [],
  "room_occupancy": [],
  "device_summary": {
    "total": 12,
    "active": 9,
    "offline": 2,
    "controllable": 8
  },
  "insights": [],
  "degraded": false,
  "generated_at": "2026-03-09T08:00:00Z"
}
```

#### 设计要点

- 以家庭为边界输出完整总览
- 成员、房间、设备都允许为空数组
- `degraded=true` 用来表示缓存或外部状态缺失，但响应仍可用
- 前端不必自己拼 5 个接口去猜全局状态

### 3.4 家庭上下文配置接口

建议新增：

- `GET /api/v1/context/configs/{household_id}`
- `PUT /api/v1/context/configs/{household_id}`

#### 配置内容

- 家庭模式：`home / away / night / sleep / custom`
- 隐私模式：`balanced / strict / care`
- 自动化等级：`manual / assisted / automatic`
- 访客模式、儿童保护、老人关怀、静音时段、语音快路径
- 成员级上下文覆盖项
- 房间级策略覆盖项

#### 当前阶段策略

- 后端接口未完成前，管理台使用浏览器本地草稿承接
- 草稿结构必须与后端最终配置结构尽量一致
- 后续切换到后端接口时，页面不应重写一遍

### 3.5 基础设备动作执行接口

建议新增：

- `POST /api/v1/device-actions/execute`

#### 输入

```json
{
  "household_id": "uuid",
  "device_id": "uuid",
  "action": "turn_on",
  "params": {
    "brightness": 80
  },
  "reason": "context.fast_path"
}
```

#### 业务规则

- 设备必须属于当前家庭
- 设备必须 `controllable=true`
- 高风险设备动作需要权限校验
- 成功失败都写审计日志

### 3.6 管理台页面设计

路由：

- `/context-center`

页面由四层组成：

1. **家庭状态 Hero 区**
   - 当前家庭名称
   - 家庭模式 / 隐私模式 / 自动化等级 / HA 状态
   - 当前活跃成员
2. **关键指标仪表盘**
   - 在家成员数
   - 已占用房间数
   - 在线设备数
   - 重点关注成员数
3. **成员与房间状态面板**
   - 成员卡片：在家状态、活动状态、当前位置、置信度
   - 房间卡片：占用情况、设备数量、房间策略
4. **配置界面**
   - 家庭级策略配置
   - 成员状态演示配置
   - 房间策略配置

页面数据装配策略：

- 先并发拉 `members / rooms / devices / audit_logs`
- 当前阶段用本地草稿补齐尚未有后端的数据
- 加载过程采用 `Promise.allSettled`，避免一个接口失败导致整页废掉

---

## 4. 数据模型

### 4.1 `presence_events`

用途：保存原始在家事件。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | text pk | 事件 ID |
| household_id | text fk | 所属家庭 |
| member_id | text nullable fk | 命中的成员 |
| room_id | text nullable fk | 关联房间 |
| source_type | varchar(30) | `lock/camera/bluetooth/sensor/voice` |
| source_ref | varchar(255) | 来源引用 |
| confidence | real | 置信度 |
| payload | text(JSON) | 原始摘要 |
| occurred_at | text | 事件发生时间 |
| created_at | text | 入库时间 |

索引：

- `idx_presence_events_household_occurred_at`
- `idx_presence_events_member_id`
- `idx_presence_events_source_type`

### 4.2 `member_presence_state`

用途：保存成员当前在家快照。

| 字段 | 类型 | 说明 |
|---|---|---|
| member_id | text pk fk | 成员 ID |
| household_id | text fk | 所属家庭 |
| status | varchar(20) | `home/away/unknown` |
| current_room_id | text nullable fk | 当前房间 |
| confidence | real | 聚合后置信度 |
| source_summary | text(JSON) | 来源摘要 |
| updated_at | text | 更新时间 |

说明：

- 每个成员最多只有一条当前快照
- 不记录历史，历史由 `presence_events` 承担

### 4.3 `context_configs`

用途：保存家庭级上下文配置。

| 字段 | 类型 | 说明 |
|---|---|---|
| household_id | text pk fk | 所属家庭 |
| config_json | text(JSON) | 家庭、成员、房间配置草案 |
| version | integer | 版本号 |
| updated_by | text nullable | 最后修改人 |
| updated_at | text | 更新时间 |

设计理由：

- 配置结构仍在演进，用 JSON 比拆 5 张小表更稳
- 首期写少读多，JSON 查询性能不是问题
- 只要边界校验做好，复杂度远低于过早正规化

### 4.4 `Redis` 热缓存键设计

- `context:household:{household_id}:overview`
- `context:household:{household_id}:member_presence`
- `context:household:{household_id}:room_occupancy`
- `context:household:{household_id}:active_member`

### 4.5 前端本地草稿结构

当前阶段 `Admin Web` 使用浏览器本地存储，结构与 `context_configs.config_json` 对齐：

```json
{
  "home_mode": "home",
  "privacy_mode": "balanced",
  "automation_level": "assisted",
  "home_assistant_status": "healthy",
  "active_member_id": "uuid 或 null",
  "voice_fast_path_enabled": true,
  "guest_mode_enabled": false,
  "child_protection_enabled": true,
  "elder_care_watch_enabled": true,
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "member_states": [],
  "room_settings": []
}
```

---

## 5. 正确性属性与业务不变量

### 5.1 家庭边界不变量

- 任何成员、房间、设备、配置都必须属于同一个 `household_id`
- 跨家庭引用一律拒绝

### 5.2 成员快照不变量

- 一个成员只能有一条当前快照
- 当前快照由最新有效事件聚合得到
- 低置信度不能伪装成高确定状态

### 5.3 房间占用不变量

- 房间占用只由“当前在家且定位明确”的成员快照推导
- 没有成员时房间状态必须是空或未知，不能凭空有人

### 5.4 活跃成员不变量

- 活跃成员必须是当前家庭成员
- 活跃成员必须与当前在场上下文一致，否则应为 `null`

### 5.5 配置一致性不变量

- 配置中的 `member_id` 和 `room_id` 必须存在于当前家庭
- 删除成员或房间后，配置引用必须被清理或忽略

### 5.6 审计不变量

- 设备动作执行、配置保存、同步任务等关键动作都必须可追踪
- 失败也要留痕，不能只记成功不记失败

---

## 6. 错误处理

### 6.1 外部系统错误

#### `Home Assistant` 不可用

处理策略：

- 设备同步或动作执行返回失败
- 审计写 `fail`
- 上下文总览将 `home_assistant_status` 标为 `degraded` 或 `offline`

### 6.2 事件输入错误

#### 非法来源、非法家庭、非法房间

处理策略：

- 拒绝写入
- 返回明确字段错误
- 不允许脏事件污染聚合链路

### 6.3 缓存错误

#### `Redis` 失效或不可达

处理策略：

- 从 `SQLite` 快照降级查询
- 响应中标记 `degraded=true`
- 写日志记录降级发生

### 6.4 前端部分数据加载失败

处理策略：

- 页面使用 `Promise.allSettled`
- 可展示部分继续展示
- 顶部给出明确错误提示
- 不把整个页面变成白板

---

## 7. 测试策略

### 7.1 单元测试

覆盖：

- 在家事件校验
- 成员快照聚合逻辑
- 房间占用推导逻辑
- 配置 JSON 校验与归一化

### 7.2 接口集成测试

覆盖：

- `POST /context/presence-events`
- `GET /context/overview`
- `PUT /context/configs/{household_id}`
- `POST /device-actions/execute`

验证点：

- 正常路径
- 非法家庭边界
- 缓存降级路径
- 审计写入

### 7.3 前端验证

覆盖：

- `apps/admin-web` 构建通过
- 家居上下文页在有/无家庭场景下可用
- 本地草稿刷新后可恢复
- 家庭切换后仪表盘和配置同步切换

### 7.4 人工联调

覆盖：

- 真实 `Home Assistant` 同步成功
- 模拟在家事件写入后，上下文总览能反映变化
- 前端配置与后端配置结构对齐

---

## 8. 风险与回滚策略

### 8.1 最大风险

1. 事件噪声太大，导致成员状态来回抖动
2. 配置结构过早拆细，导致前后端一起复杂化
3. 前端先做原型但数据结构没钉死，后面重写一遍

### 8.2 应对策略

1. 原始事件与聚合快照分层保存
2. 配置首期收敛到一张 JSON 表
3. 前端原型严格贴近后端计划结构
4. 对低置信度结果默认保守处理

### 8.3 回滚策略

- 新接口可按路由和功能开关独立关闭
- 管理台页面可退回只读模式
- 缓存不可用时退回数据库快照查询
