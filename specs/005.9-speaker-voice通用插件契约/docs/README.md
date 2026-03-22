# 005.9 补充文档

这份目录放 `speaker/voice` 通用插件契约的补充材料。

本 Spec 落地时，建议至少补下面这些文档：

- `speaker-adapter-manifest示例.md`
  说明第三方 `speaker/voice` 插件的 manifest 最小写法。
- `text-turn时序图.md`
  说明文本轮询型实时对话从插件 runtime 到宿主对话链的时序。
- `audio-session边界说明.md`
  说明音频会话型接入和文本轮询型接入的差别，避免假实时设计。
- `禁用与错误语义对照表.md`
  把插件禁用、离线、降级、心跳丢失等状态讲清楚。

当前先不展开写，是因为这份 Spec 先把主文档边界立住。
