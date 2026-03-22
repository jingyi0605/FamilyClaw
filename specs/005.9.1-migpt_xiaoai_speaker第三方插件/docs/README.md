# 005.9.1 补充文档

这份目录放 `migpt_xiaoai_speaker` 第三方插件的补充材料。

建议后续补这些文档：

- `migpt源码分析结论.md`
  把 MiNA 会话轮询、MIoT 指令、TTS 播放、播放状态检测这些结论整理成可读版本。
- `实例配置示例.md`
  给出插件实例配置示例和字段解释。
- `机型profile模板.md`
  说明 `ttsCommand`、`wakeUpCommand`、`playingCommand` 该怎么建模。
- `风控与恢复策略.md`
  说明登录失效、风控、轮询失败后的降级和恢复边界。

当前先不展开，是因为主文档要先把边界钉死。
