# 004.9 设计文档：插件来源模型降级与安装方式收口

## 1. 设计目标

目标很简单：

1. 删除 `official` 作为正式运行时来源语义。
2. 把第三方插件安装方式收口为 `local` / `marketplace`。
3. 让 `plugins-dev` 成为可加载的开发源码目录。
4. 同 `plugin_id` 的开发版和已安装版并存可见，但同一时刻只启用一个。
5. 保证 `builtin` 永远最高优先级。

## 2. 目录模型

### 2.1 当前正式目录

```text
apps/api-server/
  app/plugins/builtin/
  plugins-dev/
  data/plugins/third_party/local/
  data/plugins/third_party/marketplace/
```

### 2.2 目录职责

- `app/plugins/builtin/`
  内置插件源码目录，跟宿主一起交付。
- `plugins-dev/`
  第三方插件开发源码目录，会参与插件发现，但不是安装目录。
- `data/plugins/third_party/local/`
  本地安装产物目录。
- `data/plugins/third_party/marketplace/`
  市场安装产物目录。

### 2.3 已废弃目录

- `apps/api-server/data/plugins/official/`
- `apps/api-server/data/plugins/third_party/manual/`

它们只保留历史兼容意义，不再作为当前实现依据。

## 3. 家庭插件注册表的组装算法

### 3.1 基本顺序

注册表构建时先收集三类来源：

1. `builtin`
2. 已安装 third_party
3. `plugins-dev`

### 3.2 冲突规则

#### `plugins-dev` 和 `builtin` 同名

- 跳过开发版。
- 保留 `builtin`。
- 记录日志。

#### `plugins-dev` 和已安装 third_party 同名

- 不再把已安装版直接隐藏掉。
- 注册表里保留两个变体：开发版、已安装版。
- 前端插件管理页必须能同时看到这两个变体。

### 3.3 启用规则

- 同一个 `plugin_id` 的第三方变体，同一时刻只允许启用一个。
- 默认优先开发版。
- 当用户切换到已安装版时，宿主负责把同名开发版自动切到非启用态。
- 当用户再切回开发版时，宿主负责把同名已安装版自动切到非启用态。

这里的“优先开发版”说的是默认启用策略，不是“把安装版记录覆盖没”。

## 4. plugins-dev 的行为边界

### 4.1 会做的事

- 扫描 `plugins-dev` 下的 `manifest.json`
- 基于开发目录生成插件注册项
- 作为开发版进入插件管理页
- 在存在同名安装版时，成为默认启用变体

### 4.2 不会做的事

- 不写数据库挂载记录
- 不参与安装目录生成
- 不参与本地安装、市场安装、卸载和清理
- 不替代启动同步逻辑

### 4.3 market/local 语义保留

即使存在同名开发版，已安装变体的这些状态也必须保留：

- `install_method`
- `marketplace_instance_id`
- `install_status`
- `config_status`
- `installed_version`
- `update_state`
- `version_governance`

原因很简单：开发版参与运行，不等于安装语义消失。

### 4.4 前端展示必须显式暴露

前端不能再靠 `manifest_path`、目录路径或 `install_method` 去猜谁在运行。

后端必须显式给出至少两类信息：

- 当前记录是开发版还是已安装版
- 当前是否是“开发插件生效中”

前端插件列表和插件详情必须直接根据这些字段显示：

- “开发版” / “已安装版”
- “开发插件生效中”

## 5. 启动同步和安装逻辑

### 5.1 启动同步只看安装态目录

启动同步只扫描：

- `third_party/local`
- `third_party/marketplace`

它负责恢复安装态挂载，不负责把开发源码写成安装态。

### 5.2 本地安装

本地安装产物写入：

```text
data/plugins/third_party/local/<household_id>/<plugin_id>/<release_dir>/
```

### 5.3 市场安装

市场安装产物写入：

```text
data/plugins/third_party/marketplace/<household_id>/<plugin_id>/<version>/
```

### 5.4 删除安装态

删除安装态时：

- 只删安装目录
- 不删 `plugins-dev`
- 如果 `plugins-dev` 里有同名开发版，删除安装产物后开发版仍然可见、可启用

## 6. 兼容迁移

### 6.1 数据层

- `official` 映射为 `third_party`
- `trusted_level` 收口到 `is_system`
- `manual` 收口到 `local`

### 6.2 文件系统

- 历史 `official/marketplace` 迁移到 `third_party/marketplace`
- 历史仓库内“官方插件开发目录”迁移到 `plugins-dev`

### 6.3 文档层

- 正式文档只讲 `builtin` / `third_party` 和 `local` / `marketplace`
- 旧 spec 里保留历史路径时，必须明确标成“历史说明，已废弃”

## 7. 测试策略

### 7.1 单元与集成测试覆盖点

- `plugins-dev` 中的开发版会进入注册表
- `plugins-dev` 和已安装 third_party 同名时，两个变体都能被查询到
- 同名第三方变体只能同时启用一个
- 默认优先开发版
- 可以直接切换到已安装版验证，不需要移动目录
- `plugins-dev` 不能覆盖 `builtin`
- 启动同步不会为 `plugins-dev` 创建 mount
- marketplace 安装态信息在存在开发版时仍然保留

### 7.2 测试隔离

测试环境中的 `plugin_dev_root` 必须指向独立空目录，避免真实仓库 `plugins-dev` 污染单测结果。

## 8. 当前设计结论

这次设计不是再发明一个“官方插件层”，而是把旧模型里的脏概念拆掉：

- 运行时只保留 `builtin` 和 `third_party`
- 第三方只按安装方式区分
- `plugins-dev` 是开发源码目录，不是安装目录
- 同名开发版和已安装版并存可见、互斥启用、默认开发版

这样数据结构才终于像人写的，不像补丁堆出来的。
