# 眼部后极照明 Zemax 可审计批次

本目录由实验程序生成，批次身份记录在 `manifest.json`。生成 ZIP 只代表近轴模型输入已经冻结，`execution_state` 初始为 `NOT_RUN_IN_ZEMAX`；只有 `verification_report.json` 的 `verification_status` 为 `PASS`，才能称该批次已经由真实 OpticStudio 验证。

## 一条命令执行

将 ZIP 解压到一个新目录，在 Windows PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_zemax_batch.ps1 `
  -OpticStudioDir "C:\path\to\Ansys Zemax OpticStudio"
```

也可以先设置环境变量，再省略参数：

```powershell
$env:ZEMAX_OPTICSTUDIO_DIR = "C:\path\to\Ansys Zemax OpticStudio"
powershell -ExecutionPolicy Bypass -File .\scripts\run_zemax_batch.ps1
```

运行器会启动一个无界面的 ZOS-API Standalone Application。执行前请保存其他 OpticStudio 工作，并确保许可证允许新增 standalone 实例。

## 批次内容

- `manifest.json`：批次 ID、模型契约、案例数、每个输入/脚本的 SHA-256。
- `cases.csv`：只包含服务器重新计算并验证过的 Zemax 输入。
- `expected_results.csv`：Python 模型对四条边界光线的预期值和允差。
- `model_snapshot/`：生成本批次时使用的模型及配置快照。
- `scripts/ZosApiEyeBatch.cs`：通用 C# ZOS-API 顺序模式执行器。
- `scripts/run_zemax_batch.ps1`：编译、运行、验证的一键入口。
- `scripts/verify_zemax_results.py`：与 C# 执行器独立的结果校验器。

## PASS 的含义

每个案例都会创建一个新的顺序模式系统，设置 650 nm 波长、物高、瞳孔、可选外置近轴负镜和固定焦距等效眼，保存 `.zos`，再用 `CreateDirectUnpol` 追迹四条近轴光线。执行器从指定的光源边界高度和眼球 stop 高度反算每条光线的初始方向，因此加入外镜时不会把“入瞳归一化坐标”误当成“眼球瞳孔物理高度”。验证器要求：

1. ZIP 中所有被清单覆盖的文件哈希完全一致；
2. 案例集合与输入哈希完全一致，不能缺行或多行；
3. OpticStudio 报告有效 ZOS-API 许可证和明确版本；
4. 每个案例有四条无错误、无渐晕的有效光线；
5. C# 和 Python 独立计算的预期边界一致；
6. Zemax 观测边界误差不超过 `expected_results.csv` 的阈值；
7. 每个 `.zos` 文件存在，且哈希与 `zos_results.csv` 一致。

## 输出目录

每次运行写入新的 `runs/<batch-id>_<UTC-run-id>/`，默认拒绝覆盖。关键输出为：

- `zos_results.csv`
- `run_metadata.json`
- `systems/*.zos`
- `verification_report.json`
- `runner.log` 和 `compile.log`

`_build/` 只包含本机编译产物和从 OpticStudio 安装目录复制的 API 程序集，不属于实验结果证据。

## 安全与限制

- 不要把许可证信息、安装目录或包含个人信息的完整日志提交到公共仓库。
- 当前系统是等效近轴眼，不是完整角膜—前房—晶状体解剖模型。
- `DirectUnpol` 的非偏振近轴追迹不验证偏振、镀膜、菲涅耳反射和体吸收；本批次验证的是近轴几何映射，不是绝对视网膜辐照度或生物安全。
- 如果本机 OpticStudio 版本的 API 与脚本不兼容，应以该版本随附的 C# Standalone Application 示例为准进行适配，并把适配作为新版本记录，不能伪造成功结果。
