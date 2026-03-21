# 004.9 设计文档：插件来源模型降级与安装方式收口

## 1. 设计目标

目标很简单：

1. 删除 `official` 作为正式运行时语义
2. 把第三方插件的安装行为收口为 `local` / `marketplace`
3. 让 `plugins-dev` 参与开发态加载和第三方覆盖
4. 保证 `builtin` 永远最高优先级

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
  内置插件源码目录，跟宿主一起交付
- `plugins-dev/`
  第三方插件开发源码目录，也是开发覆盖源
- `data/plugins/third_party/local/`
  本地安装产物目录
- `data/plugins/third_party/marketplace/`
  市场安装产物目录

### 2.3 已废弃目录

- `apps/api-server/data/plugins/official/`
- `apps/api-server/data/plugins/third_party/manual/`

它们只保留历史兼容意义，不再作为当前实现依据。

## 3. 家庭插件注册表的组装算法

### 3.1 顺序

家庭插件注册表按下面顺序组装：

1. 先收集 `builtin`
2. 再收集安装态 third_party mount
3. 最后扫描 `plugins-dev`，把开发态插件合入

### 3.2 冲突规则

- `plugins-dev` 与 `builtin` 同名：跳过开发插件，记录日志
- `plugins-dev` 与已安装 third_party 同名：开发插件覆盖运行态 manifest、entrypoint、runner 配置
- 只有 `plugins-dev` 存在该插件：直接作为开发态第三方插件加入家庭注册表

### 3.3 固定优先级

`builtin > plugins-dev > 已安装 third_party`

这是硬规则，不给配置开口子。

## 4. plugins-dev 的行为边界

### 4.1 会做的事

- 扫描 `plugins-dev` 下的 `manifest.json`
- 基于开发目录生成 `PluginRegistryItem`
- 以 `subprocess_runner` 方式提供执行入口
- 在家庭插件注册表中覆盖第三方插件

### 4.2 不会做的事

- 不写数据库挂载记录
- 不参与安装目录生成
- 不参与市场安装、本地安装、卸载和清理
- 不替代启动同步逻辑

### 4.3 market/local 语义保留

当 marketplace 插件被开发版覆盖时，以下状态必须保留：

- `install_method`
- `marketplace_instance_id`
- `install_status`
- `config_status`
- `installed_version`
- `update_state`
- `version_governance`

原因很简单：开发覆盖只替换运行时代码和 manifest，不抹掉安装语义。

### 4.4 开发覆盖态要显式暴露给前端

家庭插件注册表里，开发覆盖态不能靠 `manifest_path`、`install_method` 之类的旁路信息推断。

当前实现要额外暴露一个明确字段：

- `is_dev_active=true`：当前家庭实际生效的是 `plugins-dev` 版本
- `is_dev_active=false`：当前家庭跑的是内置插件或安装态第三方插件

前端插件列表和插件详情直接根据这个字段显示“开发插件生效中”标签。

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
- 如果 `plugins-dev` 里有同名插件，删除后家庭注册表里仍然能看到开发版

## 6. 兼容迁移

### 6.1 数据层

- `official` 映射为 `third_party`
- `trusted_level` 收口到 `is_system`
- `manual` 收口到 `local`

### 6.2 文件系统

- 历史 `official/marketplace` 迁移到 `third_party/marketplace`
- 历史仓库内“官方插件开发目录”迁移到 `plugins-dev`

### 6.3 文档层

- 正式文档只讲 `builtin` / `third_party` 与 `local` / `marketplace`
- 历史 spec 中保留旧路径时，必须明确标注“历史说明，已废弃”

## 7. 测试策略

### 7.1 单元与集成测试覆盖点

- `plugins-dev` 覆盖已安装 third_party
- `plugins-dev` 不能覆盖 `builtin`
- `plugins-dev` 开发插件无 mount 也能进入家庭注册表
- 启动同步不会为 `plugins-dev` 创建 mount
- marketplace 插件被开发版覆盖时，市场状态语义仍保留
- 删除安装态后，开发插件仍然可见

### 7.2 测试隔离

测试环境中的 `plugin_dev_root` 必须指向独立空目录，避免仓库真实 `plugins-dev` 污染单测结果。

## 8. 当前实现结论

这次设计不是“再发明一个官方插件层”，而是反过来把旧层级砍掉：

- 运行时只有 `builtin` 和 `third_party`
- 第三方只按安装方式区分
- `plugins-dev` 只是开发覆盖源

这样数据结构才终于像人写的，不像补丁堆出来的。
