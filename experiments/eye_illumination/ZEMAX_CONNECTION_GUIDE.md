# 实验程序连接 Ansys Zemax OpticStudio：完整操作与审计指南

## 1. 接入目标与可信边界

本实验程序采用“两阶段”连接方式：网页程序负责参数选择、范围约束、批次冻结和解析预期值；ZOS-API Standalone Application 负责在真实 OpticStudio 中建立顺序系统、批量追迹、保存 `.zos`；独立 Python 校验器负责把输入、Zemax 输出和文件哈希逐项核对。

```text
浏览器实验台
  └─ 经过范围校验的结果表
      └─ 确定性 Zemax ZIP（batch_id + SHA-256）
          └─ C# ZOS-API Standalone Application
              ├─ systems/*.zos
              ├─ zos_results.csv
              └─ run_metadata.json
                  └─ 独立 Python verifier
                      └─ verification_report.json: PASS / FAIL
```

这种设计不会把“程序算出结果”和“Zemax 已验证”混在一起：ZIP 清单初始明确写为 `NOT_RUN_IN_ZEMAX`；只有真实 ZOS-API 运行完成且最终报告为 `PASS` 才算完成 Zemax 验证。

## 2. 为什么选择 Standalone 批处理

Ansys 官方资料说明，ZOS-API 可以使用 Standalone 模式启动独立的后台 OpticStudio，也可以通过其他模式连接已打开的实例。本实验选择 C# Standalone 模式，因为批次输入和输出目录可以完全固定，不依赖 GUI 当前打开了什么文件，也不会修改用户正在查看的系统。

官方参考：

- [Ansys：ZOS-API 示例代码与连接模式](https://optics.ansys.com/hc/en-us/articles/42661773562899-Sample-code-for-ZOS-API-users)
- [Ansys：ZOS-API.NET 概览](https://optics.ansys.com/hc/en-us/articles/42661790380179-ZOS-API-NET-An-Overview)
- [Ansys Help：Standalone Applications](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v251/en/OpticStudio_User_Guide/OpticStudio_Help/topics/ZOS_Standalone_Applications_Your_Application_Uses_ZOS.html)
- [Ansys Help：Batch Ray Trace Modes](https://ansyshelp.ansys.com/public/Views/Secured/Zemax/v252/en/OpticStudio_User_Guide/OpticStudio_Help/topics/Batch_Ray_Trace_Modes_%28About_the_ZOS-API%29.html)

## 3. Windows 前置条件

1. 安装 Ansys Zemax OpticStudio，并确认 GUI 能正常打开。
2. 许可证必须允许 ZOS-API。Standalone 会启动一个新的后台实例；运行前保存其他工作，并留意许可证并发限制。
3. 安装 64 位 Python 3.11 或更高版本。Python 架构应与 OpticStudio API 运行环境一致。
4. Windows 需要 64 位 .NET Framework C# 编译器。脚本会检查 `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`。
5. OpticStudio 安装目录必须含 `ZOSAPI.dll`、`ZOSAPI_Interfaces.dll` 和 `ZOSAPI_NetHelper.dll`。

不要从网络下载不明 DLL，也不要假设安装路径。可以在 OpticStudio 的 Programming 页面打开 ZOS-API Help 和 C# Standalone Application 示例，把本机示例所引用的程序集和初始化方式作为最终依据。

## 4. 推荐方式：网页三步验证向导

第一次使用双击 `app/setup_local.cmd`，以后双击 `app/launch_app.cmd`。浏览器打开后滚动到“04 Zemax 验证向导”：

1. **检测本机环境**：点击“自动检测 OpticStudio”。程序只读取安装目录、Python 架构、C# 编译器和三个 ZOS-API DLL，不会启动 OpticStudio，也不会把许可证写成已验证。
2. **先验证 1 个工况**：勾选明确确认框后才能点击。网页把当前工况在服务器端重新计算，启动一个 Standalone OpticStudio，保存 `.zos` 并运行独立校验器。
3. **查看 PASS / FAIL**：只有真实 API 许可证有效、案例无缺失、四条边界光线有效且无渐晕、误差在阈值内、`.zos` 和哈希匹配时才显示 PASS。PASS 后才解锁当前结果表的批量运行。

任务运行期间不要关闭启动窗口。为保护许可证，应用同一时刻只允许一个 Zemax 任务。下载的证据包包含输入快照、验证报告、CSV 和系统文件，不包含 `_build`、编译日志或本机绝对路径配置。

如果自动发现了错误版本，可展开“高级设置”，手动选择直接包含 `ZOSAPI.dll` 的安装目录。路径只保留在当前网页会话和本机运行进程中，不会写入仓库。

## 5. 命令行备用方式：从网页生成离线批次

1. 启动实验程序：

   ```powershell
   powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1
   ```

2. 打开 `http://127.0.0.1:8765/`。
3. 选择固定三焦距基准或 PPT 参数范围模式。
4. 先运行当前工况；按需生成 21 行敏感性表、三水平范围网格或完整 252 工况。
5. 点击“生成 Zemax 审计批次”。程序只把当前表格的独立输入发回本机服务器；服务器会逐行重新计算，拒绝超范围、重复或被篡改的工况。
6. 保存下载的 `eye-zemax-<16位哈希>.zip`。相同输入、模型版本和脚本会生成完全相同的 batch ID 和 ZIP SHA-256。

## 6. 运行离线批次

把 ZIP 解压到新目录，例如 `C:\eye-zemax\eye-zemax-xxxxxxxxxxxxxxxx`，然后运行：

```powershell
Set-Location C:\eye-zemax\eye-zemax-xxxxxxxxxxxxxxxx
powershell -ExecutionPolicy Bypass -File .\scripts\run_zemax_batch.ps1 `
  -OpticStudioDir "C:\path\to\installed\OpticStudio"
```

如果经常使用同一安装，可以设置仅在当前终端有效的环境变量：

```powershell
$env:ZEMAX_OPTICSTUDIO_DIR = "C:\path\to\installed\OpticStudio"
powershell -ExecutionPolicy Bypass -File .\scripts\run_zemax_batch.ps1
```

可选参数：

- `-PythonPath "C:\path\to\python.exe"`：显式指定验证器使用的 Python。
- `-OutputRoot "D:\approved\eye-runs"`：把运行证据写到指定根目录。
- `-RunId "instrument-A-repeat-01"`：指定可审计重复编号，只允许字母、数字、点、下划线和连字符。

脚本始终创建新的 `<batch-id>_<run-id>` 目录，并拒绝覆盖同名目录。它先编译 C# 执行器，再启动 OpticStudio，最后无条件运行独立验证器；任一阶段失败都会返回非零退出码。

## 7. Zemax 中建立的模型

每个案例从一个新的 Sequential System 开始：

1. Object surface 到等效眼的距离等于 `1000 / 物方需求(D)`。
2. 如果外置负镜不为 0 D，在离眼球指定顶点距处插入 Paraxial surface；焦距为 `1000 / 外镜度数`。
3. 等效眼使用固定的 Paraxial surface；焦距来自该案例，不由物距自动拟合。
4. 眼表面被设为 stop，孔径等于所选瞳孔。
5. 眼表面到 Image surface 的距离为 `眼轴 / 像方折射率`，对应程序的约化后极距离。
6. 波长使用 0.650 µm。
7. Object Height 为保守光源半径，追迹光源高度比例 `±1`、眼球 stop 高度比例 `±0.99` 的四条直接、近轴、非偏振光线。执行器利用外镜前的 ABCD 矩阵反算初始方向，使指定的 stop 高度是物理瞳孔高度，而不是会随外镜变化的归一化入瞳坐标。选择 Paraxial ray type 是为了严格匹配 ABCD 等效眼契约；真实光线、像差和能量验证应作为后续独立模型版本，不能混入本批次判据。

Ansys 文档指出，归一化非偏振批量追迹会检查 ray error 和 vignette，但忽略偏振、镀膜、菲涅耳反射和体吸收。因此本验证只证明等效近轴几何映射一致，不证明绝对能量或组织安全。

## 8. 审计文件和判定规则

输入证据：

- `manifest.json`：批次 ID、模型契约和包内文件哈希。
- `cases.csv`：Zemax 的唯一输入表。
- `expected_results.csv`：Python 预期边界和每行允差。
- `model_snapshot/`：模型与配置快照。

运行证据：

- `zos_results.csv`：每行的版本、许可证状态、预期/观测边界、误差、有效光线数、错误数、渐晕数、`.zos` 路径及哈希。
- `run_metadata.json`：UTC 起止时间、OpticStudio 版本、批次哈希和完成/失败计数。
- `systems/*.zos`：每个工况的可复查顺序系统。
- `compile.log`、`runner.log`：诊断日志。

最终证据：

- `verification_report.json`：唯一的 PASS/FAIL 总结，并封存结果文件 SHA-256。

`PASS` 要求包完整、案例集合完全相等、有效 API 许可证、每案例四条有效且无渐晕光线、C# 与 Python 的预期边界一致、Zemax 误差不超过阈值、所有 `.zos` 存在且哈希一致。任何缺行、额外行、哈希变化、无许可证、API 异常或数值超差都会得到 `FAIL`。

## 9. 人工在 OpticStudio GUI 中抽查

自动验证通过后，建议随机抽查至少三个案例：小鸡、儿童和成人各一个。

1. 从 `systems/` 打开 `.zos`。
2. 在 Lens Data Editor 检查 Object thickness、可选外镜、固定等效眼焦距、Stop、瞳孔和 Image distance。
3. 在 System Explorer 检查 wavelength 为 0.650 µm、field type 为 Object Height。
4. 使用 Single Ray Trace 或 Ray Fan 检查边界光线趋势。
5. 将文件 SHA-256 与 `zos_results.csv` 对比；GUI 保存会改变文件哈希，应另存为复核副本，不能覆盖证据文件。

## 10. 失败排查

| 现象 | 检查 |
|---|---|
| 找不到 OpticStudio | 显式传入 `-OpticStudioDir`；确认三个 ZOS-API DLL 存在。 |
| 许可证无效 | 先在 GUI 验证许可证；关闭多余实例；检查许可证是否允许 ZOS-API。 |
| C# 编译失败 | 查看 `compile.log`；用本机版本的官方 C# Standalone 示例核对引用与 API。 |
| API 初始化或连接失败 | 查看 `runner.log`；确认安装目录与 DLL 来自同一 OpticStudio 版本。 |
| 某些案例 ERROR | 查看 `zos_results.csv` 的 `error_type/error_message`；不要删除失败行。 |
| `verification_status=FAIL` | 先看顶层 `issues`，再看 `case_findings`；修正后生成新运行目录，不覆盖旧证据。 |
| 外镜案例出现机械顺序错误 | 外镜顶点距必须严格小于光源距离；回到网页程序降低物方需求或选 0 D 外镜。 |
| 哈希不一致 | 输入包或 `.zos` 在运行后被修改；重新解压原 ZIP 并建立新 RunId。 |

## 11. 版本升级和可重复性纪律

- OpticStudio 升级后，先用一个小批次验证，再运行完整矩阵。
- 不直接编辑 ZIP 中的 CSV 或脚本；参数变更必须回到网页程序生成新的 batch ID。
- 重复测量使用同一个 ZIP 和不同 RunId，这样输入哈希相同、运行证据彼此独立。
- 仓库无论设为私有还是公开，都只保存脱敏后的批次清单、数值结果、验证报告和必要 `.zos`；不要提交许可证、个人路径或完整机器日志。
- 当前等效眼模型没有足够信息把 PPT 中所有角膜和晶状体部件参数独立追迹。获得完整曲率、折射率、厚度和间隔后，应建立新的解剖模型版本与新 schema，不能静默改变现有模型契约。
