# 需求文档 - 插件配置协议与动态表单

状态：Active

## 更新记录

- 2026-03-19
  - 把“静态枚举表单”升级为“支持动态选项源和字段联动的通用配置协议”。
  - 正式补充 `option_source`、`depends_on`、`clear_on_dependency_change` 和 `clear_fields` 语义。
  - 明确宿主必须提供配置草稿解析接口，前端字段变化后重新拉取可用选项。
  - 用官方天气插件作为落地案例：动态拉地区 provider，再按 provider 拉省、市、区县。

## 简介

之前这套插件配置协议，只解决了“宿主能按 schema 画出一个表单”。

它没解决更麻烦、也更真实的问题：

- 下拉选项只能写死在 manifest 里
- 字段变化后，后端不会重算下一层选项
- 前端不会清理已经失效的子级值
- 普通字段没有正式的“显式清空”语义

这套东西一旦碰上地区目录、级联 provider、多实例配置，就会立刻露馅。

天气插件就是活证据：

- 它被迫把中国大陆省市区整包写进 manifest
- 插件安装了新的地区包以后，表单根本读不到
- 父级切换后，子级值还会残留旧数据

这次更新的目标很直接：

**把插件配置从“能渲染表单”升级成“能处理动态选项和联动状态”的正式宿主能力。**

## 术语表

- **配置协议**：插件在 manifest 中声明字段、校验和 UI 提示的结构。
- **动态选项源**：不是把 `enum_options` 写死，而是让宿主在运行时按当前表单值去解析可用选项。
- **字段联动**：父字段变化后，宿主重新计算子字段选项，并清理失效值。
- **配置草稿解析**：不落库，只根据当前草稿值返回“此刻这张表单应该长什么样”。
- **普通字段清空**：通过 `clear_fields` 显式删除已保存的非 secret 字段。

## 范围说明

### In Scope

- 插件 manifest 的动态选项源声明
- 配置字段依赖和联动清理语义
- 配置草稿解析接口
- 普通字段 `clear_fields` 语义
- 宿主前端动态联动表单
- 官方天气插件改成动态地区 provider + 省市区级联

### Out of Scope

- 任意远程脚本表达式控制表单
- 通用搜索联想输入框体系
- 低代码表单设计器
- 插件自定义前端组件注入
- 所有旧插件一次性改完

## 需求

### 需求 1：插件必须能声明动态选项源和字段依赖

**用户故事：** 作为插件开发者，我希望 manifest 不只支持静态枚举，还能声明“这个字段的选项要按当前值动态计算”，这样宿主才能做正式联动，而不是继续写特判。

#### 验收标准

1. WHEN 插件声明 `enum` / `multi_enum` 字段 THEN System SHALL 支持二选一的选项来源：静态 `enum_options` 或动态 `option_source`。
2. WHEN 插件声明字段依赖 THEN System SHALL 支持 `depends_on` 和 `clear_on_dependency_change` 语义。
3. WHEN 插件声明了宿主不支持的动态源类型或非法依赖引用 THEN System SHALL 在 manifest 校验阶段明确拒绝。

### 需求 2：宿主必须提供配置草稿解析接口

**用户故事：** 作为前端开发者，我希望字段变化后能拿当前草稿去问后端“现在这张表单该长什么样”，而不是自己硬猜选项和清空规则。

#### 验收标准

1. WHEN 前端打开配置表单 THEN System SHALL 返回按当前已保存值解析后的 `config_spec`。
2. WHEN 前端提交当前草稿值到解析接口 THEN System SHALL 返回按这些值重算后的 `config_spec` 和 `view`。
3. WHEN 动态源依赖的父字段还没选好 THEN System SHALL 返回空选项列表，而不是伪造默认选项。

### 需求 3：前端必须在字段变化后联动刷新并清理失效值

**用户故事：** 作为家庭管理员，我希望我改了上一级选项后，下一级候选能立刻刷新，旧的无效值也能自动清掉，不要保存一堆脏数据。

#### 验收标准

1. WHEN 父字段变化后 THEN System SHALL 重新解析受影响字段的候选项。
2. WHEN 子字段当前值不在新候选里 THEN System SHALL 清除该值，并继续向下游传播联动。
3. WHEN 字段因 `visible_when` 变为隐藏 THEN System SHALL 支持通过正式语义清空不再适用的已保存值。

### 需求 4：普通字段和 secret 字段都必须有正式清空语义

**用户故事：** 作为系统维护者，我希望“保留旧值”和“显式清空”都走协议，而不是靠页面偷着省略字段。

#### 验收标准

1. WHEN 用户希望删除普通字段值 THEN System SHALL 支持 `clear_fields`，并在保存时真正从持久化数据里删除该字段。
2. WHEN 用户希望删除 secret 字段值 THEN System SHALL 继续使用 `clear_secret_fields`。
3. WHEN 同一个字段同时出现在新值提交和清空列表 THEN System SHALL 返回明确错误。

### 需求 5：地区 provider 和地区目录接口必须正式对插件开放

**用户故事：** 作为插件开发者，我希望宿主正式开放“可用地区 provider 列表”和“provider 下级地区目录”这两类数据，而不是让我直接依赖宿主内部表结构。

#### 验收标准

1. WHEN 插件声明 `region_provider_list` 动态源 THEN System SHALL 返回当前家庭可用的地区 provider 列表。
2. WHEN 插件声明 `region_catalog_children` 动态源 THEN System SHALL 按 provider、国家和父级地区返回子级目录。
3. WHEN 后续安装了新的地区插件 THEN System SHALL 无需修改天气插件代码即可在表单里选择并读取该 provider。

### 需求 6：天气插件必须迁到新协议且兼容旧配置

**用户故事：** 作为项目维护者，我希望天气插件成为这套能力的第一批正式接入者，同时不把已存在的实例配置搞坏。

#### 验收标准

1. WHEN 打开天气插件实例配置 THEN System SHALL 先动态拉地区 provider，再按 provider 拉省、市、区县。
2. WHEN 用户切换省份 THEN System SHALL 重新计算城市和区县候选，并清掉旧值。
3. WHEN 旧实例仍保存 `provider_selector` 或直接保存 `region_code` THEN System SHALL 继续兼容读取，不要求用户强制重建。

## 非功能需求

### 非功能需求 1：兼容性

1. WHEN 某个字段还在使用静态 `enum_options` THEN System SHALL 保持旧协议可用，不强迫所有插件当天迁移。
2. WHEN 旧插件不知道 `clear_fields` THEN System SHALL 继续把它视为“不清空普通字段”，不破坏现有保存请求。

### 非功能需求 2：可扩展性

1. WHEN 后续需要新增新的动态源类型 THEN System SHALL 在 `option_source` 上扩展，而不是再发明第二套表单协议。
2. WHEN 后续有别的插件要做级联选择 THEN System SHALL 直接复用这套 resolve + clear 机制，而不是为天气插件保留特判。

### 非功能需求 3：可测试性

1. WHEN 动态解析出错 THEN System SHALL 返回可定位的结构化错误，而不是前端只拿到空白表单。
2. WHEN 回归天气插件地区联动 THEN System SHALL 有自动化测试覆盖 provider、province、city、district 逐级解析。

## 成功定义

- manifest 能声明动态选项源和字段依赖
- 宿主有正式的配置草稿解析接口
- 前端字段变化后会联动刷新并清理失效值
- `clear_fields` 和 `clear_secret_fields` 语义都固定下来
- 天气插件不再维护巨型静态省市区枚举
- 安装新的地区 provider 后，天气插件表单能直接选择并读取它
