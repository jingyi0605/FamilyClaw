# 设计文档 - 声纹管理前端实现

状态：Draft

## 1. 概述

### 1.1 目标

- 在 `user-app` 现有设备管理结构里补齐声纹管理入口
- 让设备级“开启声纹识别”和“公开对话”行为说清楚
- 让管理员可以完成成员声纹录入和更新
- 尽量复用 `005.3` 已有接口和后端主链，不重做体系

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7

### 1.3 技术约束

- 前端应用：`apps/user-app`
- 当前主入口必须复用 `设置 -> 设备与集成`
- 不启动新服务，不改变 `005.3` 首版算法路线
- 普通对话的识别主链仍以 `005.3` 后端实现为准
- 本 Spec 只定义前端实现和前端依赖的最小接口契约

## 2. 信息架构

### 2.1 入口选择

当前 `user-app` 里，音箱设备管理已经集中在：

- `apps/user-app/src/pages/settings/integrations/index.tsx`

这里已经具备：

- 新音箱发现与添加
- 设备列表
- 小爱音箱专属“语音设置”

所以首版不新开一页，不把入口塞去家庭概览。直接在这里扩成正式的音箱设备详情。

### 2.2 页面结构

首版设备详情采用“一个详情弹层 + 两个标签页”的结构：

1. `语音接管`
2. `声纹管理`

理由很直接：

- 现有页面已经有音箱专属设置弹窗
- 用户是在“管理某台音箱”，不是在“全局管理所有声纹”
- 把“语音接管”和“声纹管理”放在同一设备详情里，能让管理员清楚理解这台设备的语音策略

### 2.3 导航与打开方式

在设备列表中，小爱音箱卡片保留设备基础信息，同时把现有“语音设置”操作升级为“设备详情”入口。

打开详情后：

- 默认停在 `语音接管` 标签
- 管理员可切换到 `声纹管理`
- 关闭弹层后回到原设备列表，不丢当前筛选和滚动位置

## 3. 页面与交互设计

### 3.1 设备详情标签页

#### 3.1.1 语音接管标签

保留现有内容：

- 是否默认接管所有语音请求
- 响应前缀设置

这部分不重做，只做结构迁移。

#### 3.1.2 声纹管理标签

从上到下分四块：

1. 设备级身份策略卡片
2. 说明卡片
3. 成员声纹状态列表
4. 建档/更新向导入口

### 3.2 设备级身份策略卡片

这个卡片是整个页面的核心，因为它决定这台音箱的对话怎么处理。

字段和行为：

- 开关：`开启声纹识别`
- 开启时说明：
  - “系统会优先按声纹识别成员，再进入对应成员对话”
  - “识别失败时会按后端既有降级规则继续处理，不会打断语音主链”
- 关闭时说明：
  - “这台设备当前按公开对话处理，所有家庭成员都可以看到对话内容”

交互规则：

- 改开关时立即出现保存态
- 保存失败时回滚 UI
- 关闭后不隐藏成员声纹档案，因为管理员仍然可能先录好，等以后再打开

### 3.3 成员声纹状态列表

列表按当前家庭成员展示，每项至少包含：

- 成员头像或名称
- 当前状态
- 最近更新时间
- 样本数量或等价摘要
- 操作按钮

首版状态收敛成下面几类：

| 状态 | 含义 | 可见操作 |
| --- | --- | --- |
| `未建档` | 当前没有生效声纹 | `开始录入` |
| `建档中` | 已有进行中的录入任务 | `查看进度` / `继续等待` |
| `可用` | 已有生效中的声纹档案 | `更新声纹` |
| `失败` | 最近一次任务失败 | `重新录入` |
| `已停用` | 档案存在但当前不可用 | `重新录入` |

如果当前后端暂时没有家庭级汇总接口，前端首版允许用：

- `members`
- `GET /api/v1/voiceprints/members/{member_id}`

拼出这张表。

但这会有 N+1 请求，所以设计上同时保留一个推荐聚合接口，见 §4.4。

### 3.4 声纹建档向导

建档向导采用侧边弹层或二级弹窗，按步骤走，不做单页大表单。

#### 3.4.1 步骤

1. 选择成员
2. 确认设备和录入说明
3. 创建建档任务
4. 等待并展示多轮采样进度
5. 成功 / 失败结果页

#### 3.4.2 每步要做什么

第一步：选择成员

- 展示当前家庭成员
- 默认过滤掉管理员无权操作的成员情况
- 如果从成员列表按钮进来，直接带入目标成员

第二步：确认设备和录入说明

- 明确展示当前设备名
- 明确告诉用户这是给哪位成员录入
- 明确告诉用户“首版按多轮样本处理，默认 3 轮”
- 提醒在目标设备附近由该成员本人说话

第三步：创建建档任务

- 调用 `POST /api/v1/voiceprints/enrollments`
- 保存返回的 `enrollment_id`
- 进入等待状态

第四步：展示进度

- 展示当前轮次
- 展示当前状态：等待采样 / 处理中 / 成功 / 失败
- 轮询任务详情或依赖设备绑定里的 `pending_voiceprint_enrollment`

第五步：结果页

- 成功：显示“已绑定到成员”
- 失败：显示失败原因、重试入口
- 取消：允许返回列表

### 3.5 更新声纹流程

更新不单独做另一套页面，直接复用建档向导。

区别只有两点：

- 入口文案改成“更新声纹”
- 结果页文案改成“已更新该成员声纹”

这样做的好处很简单：

- 不会出现两套一样的录入流程
- 前端状态机、测试和联调都简单

## 4. 组件与接口

### 4.1 前端组件拆分

建议新增或调整下面这些组件：

| 组件 | 作用 | 主要文件 |
| --- | --- | --- |
| `SpeakerDeviceDetailDialog` | 设备详情容器，承接标签页 | `apps/user-app/src/pages/settings/components/` |
| `SpeakerTakeoverTab` | 收口现有语音接管设置 | `apps/user-app/src/pages/settings/components/` |
| `SpeakerVoiceprintTab` | 声纹管理主内容 | `apps/user-app/src/pages/settings/components/` |
| `SpeakerVoiceprintMemberList` | 成员状态列表 | `apps/user-app/src/pages/settings/components/` |
| `VoiceprintEnrollmentWizard` | 建档/更新向导 | `apps/user-app/src/pages/settings/components/` |

### 4.2 前端状态模型

#### 4.2.1 设备级状态

```ts
type SpeakerVoiceprintConfig = {
  deviceId: string;
  voiceprintIdentityEnabled: boolean;
  conversationMode: 'public' | 'voiceprint_member';
  saving: boolean;
  error: string;
};
```

其中：

- `voiceprintIdentityEnabled = false` 时，`conversationMode` 固定显示为 `public`
- `voiceprintIdentityEnabled = true` 时，`conversationMode` 显示为 `voiceprint_member`

#### 4.2.2 成员声纹状态

```ts
type MemberVoiceprintStatusSummary = {
  memberId: string;
  memberName: string;
  status: 'not_enrolled' | 'pending' | 'active' | 'failed' | 'disabled';
  sampleCount: number;
  updatedAt: string | null;
  pendingEnrollmentId: string | null;
  errorMessage: string | null;
};
```

#### 4.2.3 建档向导状态

```ts
type VoiceprintWizardState =
  | { step: 'select_member'; memberId: string | null }
  | { step: 'confirm'; memberId: string; terminalId: string }
  | { step: 'creating'; memberId: string; terminalId: string }
  | { step: 'waiting'; memberId: string; enrollmentId: string }
  | { step: 'success'; memberId: string; enrollmentId: string }
  | { step: 'failed'; memberId: string; enrollmentId: string | null; error: string };
```

### 4.3 直接复用的现有接口

首版前端优先复用下面这些接口：

- `GET /api/v1/devices?household_id=...`
- `PATCH /api/v1/devices/{device_id}`
- `GET /api/v1/voiceprints/enrollments`
- `GET /api/v1/voiceprints/enrollments/{enrollment_id}`
- `POST /api/v1/voiceprints/enrollments`
- `POST /api/v1/voiceprints/enrollments/{enrollment_id}/cancel`
- `GET /api/v1/voiceprints/members/{member_id}`
- `DELETE /api/v1/voiceprints/members/{member_id}`

### 4.4 推荐补齐的最小接口字段

当前设备接口已经有：

- `voice_auto_takeover_enabled`
- `voice_takeover_prefixes`

但还没有设备级声纹识别开关。为了让前端能落地，本 Spec 推荐在设备读写模型中补下面的最小字段：

#### 4.4.1 设备读写字段

```ts
type DeviceVoiceprintFields = {
  voiceprint_identity_enabled: boolean;
};
```

用途只有一个：

- 决定这台音箱是否开启“按声纹识别成员路由”

关闭时首版直接按公开对话展示，不再引入第二个无意义开关。

#### 4.4.2 推荐聚合接口

如果实现时发现前端用 `members + members/{member_id}` 拼列表太重，推荐补一个聚合查询接口：

- `GET /api/v1/voiceprints/households/{household_id}/summary?terminal_id=...`

返回：

- 设备级声纹开关状态
- 当前家庭成员声纹摘要列表
- 与该设备相关的进行中建档任务摘要

这不是新体系，只是把前端本来要拼的数据收口成一个读取接口。

### 4.5 页面文案约束

前端文案必须说人话，不许写成底层术语堆。

推荐表达：

- 开启时：
  - “优先按声纹识别成员”
  - “识别成功后进入对应成员对话”
- 关闭时：
  - “当前按公开对话处理”
  - “所有家庭成员都可以看到这台设备的对话内容”
- 失败时：
  - “这次录入没有成功，可以重新开始”

不推荐表达：

- “开启身份解析路由增强”
- “启用声纹能力闭环”
- “配置会话归属策略”

## 5. 错误处理与降级

### 5.1 错误类型

- 设备配置保存失败
- 声纹汇总读取失败
- 建档任务创建失败
- 建档任务处理中断
- 当前设备已有进行中的任务
- 用户权限不足

### 5.2 处理策略

1. 设备开关保存失败：
   - 回滚开关
   - 给出明确错误提示

2. 成员声纹列表加载失败：
   - 只让声纹区域出错
   - 设备详情其他标签继续可用

3. 建档失败：
   - 显示失败结果页
   - 保留“重新录入”入口

4. 没有管理员权限：
   - 页面可看
   - 所有修改按钮置灰并显示说明

## 6. 正确性约束

### 6.1 同一设备只表达一种前端身份策略

对于任意一台音箱，前端界面必须清楚表达它当前是：

- 公开对话
- 或按声纹识别成员

不能同时出现互相打架的描述。

### 6.2 关闭声纹识别不等于删除已有档案

关闭设备级开关时，前端只改变这台设备的路由策略展示，不自动删除成员已有声纹档案。

### 6.3 更新流程必须复用建档流程

首次录入和更新声纹必须共用一套向导主流程，避免前端维护两套分叉状态机。

## 7. 测试策略

### 7.1 单元测试

- 设备详情标签切换
- 声纹开关保存成功 / 失败
- 成员状态列表的状态映射
- 建档向导状态机切换

### 7.2 集成测试

- 从设备列表进入音箱详情，再切到声纹管理标签页
- 关闭声纹识别后显示公开对话说明
- 开启声纹识别后显示成员路由说明
- 发起首次录入并展示处理中状态
- 发起更新声纹并展示成功结果

### 7.3 手工验收

- 管理员视角检查完整流程
- 非管理员视角检查按钮禁用和说明
- 声纹区域接口失败时检查局部降级

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.1、§2.2、§3.1 | 页面结构测试 + 人工走查 |
| `requirements.md` 需求 2 | `design.md` §3.2、§4.4 | 设备开关测试 |
| `requirements.md` 需求 3 | `design.md` §3.3、§4.2.2 | 列表状态映射测试 |
| `requirements.md` 需求 4 | `design.md` §3.4、§4.2.3、§4.3 | 建档向导测试 |
| `requirements.md` 需求 5 | `design.md` §3.5、§6.3 | 更新流程测试 |
| `requirements.md` 需求 6 | `design.md` §5.2、§6.1、§6.2 | 权限和降级测试 |
| `requirements.md` 需求 7 | `design.md` §4.3、§4.4 | 接口契约走查 |

## 8. 风险与待确认项

### 8.1 风险

- 当前设备接口还没有设备级声纹开关字段，前端实现前必须先补齐
- 如果成员状态只能靠逐个接口拼装，设备详情首次打开可能会偏慢
- 设备关闭声纹后按“公开对话”处理，这部分如果后端还没显式支持，需要和后端同步最终落地字段

### 8.2 待确认项

- 设备详情最终采用抽屉还是弹窗，只要能稳定承接标签页即可
- 成员声纹摘要首版是走聚合接口，还是先用多个现有接口拼装
- 是否在成员列表中直接提供“停用声纹”入口；如果没有明确产品要求，首版先只做录入和更新
