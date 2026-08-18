# Web GUI → OpticStudio 验证证据

该目录记录 `eye-illumination-web-zemax-console-v1` 里程碑的真实 ZOS-API 验证。运行由本地 Web GUI 的三步向导显式启动，不是模拟后端结果。

- 批次：`eye-zemax-2a8b5f0189c5e6e8`
- OpticStudio：24.1.0
- ZOS-API 许可证：有效
- 工况：21 / 21 PASS，0 FAIL
- 最大边界误差：`1.7763568394002505e-12 µm`
- 证据 ZIP SHA-256：`68df9f3ff53b06e03e2446a65887fae53119f8835274dd72b7f8f2d924a8eabd`

`web_gui_zemax_21_case_evidence.zip` 含确定性输入批次、独立验证报告、结果 CSV 及 21 个 `.zos` 系统；不含 `_build`、原始日志、许可证材料或本机绝对路径配置。为便于代码审查，最终清单、元数据、验证报告和结果表另行解出为文本文件。
