# 固定焦距后极照明实验程序

这是 `eye-illumination-fixed-focal-60-120d-v3` 的本地交互应用。程序直接调用上级目录的 `eye_model.py` 和版本化参数，不会在前端复制或重新实现光学公式。应用包含两个明确分开的模式：

- **固定三焦距基准**：严格复现已验证的 252 工况矩阵。
- **PPT 参数范围探索**：允许用户手动调整 PPT 声明的有效焦距、眼轴和瞳孔范围，但不会根据物距自动反求焦距。

## 第一次使用：双击安装并启动

在 Windows 中双击 `setup_local.cmd`。它只在当前程序目录建立私有 `.venv`、安装固定范围的 NumPy 依赖，然后自动打开 Web GUI。以后只需双击 `launch_app.cmd`，无需重复安装。

等价的 PowerShell 命令：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\setup_local.ps1
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1
```

## 日常启动

Windows 下双击 `launch_app.cmd`。也可以从仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1
```

浏览器默认打开 `http://127.0.0.1:8765/`。关闭启动窗口或按 `Ctrl+C` 即可停止程序。

如果系统中的 Python 命令不是 `python`：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1 `
  -PythonPath "C:\path\to\python.exe"
```

程序要求 64 位 Python 3.11+ 和 NumPy。`setup_local.cmd` 会自动完成应用运行环境；仓库开发环境也可通过 `python -m pip install -e ".[dev,analysis]"` 安装完整依赖。

## 功能

- 从三个眼模型中选择小鸡、6 岁儿童或 18 岁成人。
- 焦距下拉框只暴露对应模型的三个固定值，不接受连续拟合值。
- 范围探索模式通过滑块接受区间内的连续值，并显示每个区间来自 PPT 还是模型灵敏度假设。
- 小鸡眼轴采用 PPT 的 10.5–12.5 mm；儿童和成人的 ±0.5 mm 仅作为透明标注的灵敏度假设。
- 支持 PPT 第 5 页的 0、-1、-3、-5、-10、-15、-20 D 外置凹透镜选项；机械顺序无效的组合会被拒绝，不会静默给出错误结果。
- 物方需求保持在 60–120 D；基准矩阵步长 10 D，范围模式滑块步长 1 D。
- 已知眼轴、后极目标和像方折射率在界面中只读显示。
- 即时输出几何最小和推荐全重叠光源尺寸。
- 绘制光源—等效透镜—固定后极的 SVG 光路示意。
- 比较三个固定焦距随物方需求变化的曲线。
- 在范围模式中可分别查看有效焦距、眼轴或瞳孔的三水平灵敏度曲线。
- 生成 21 行当前对比或完整 252 行矩阵。
- 生成当前眼模型的最小值/默认值/最大值三水平范围网格，并报告因外镜机械顺序而跳过的组合。
- 将当前工况导出为 JSON，将结果矩阵导出为带 UTF-8 BOM 的 CSV。
- 将当前结果表导出为确定性的 Zemax 审计 ZIP，内含模型快照、哈希、通用 ZOS-API runner 和独立 verifier。
- 在网页内自动发现 OpticStudio，检查 Windows、Python、C# 编译器和三个 ZOS-API DLL；只读预检不会启动 Zemax。
- 通过“三步验证向导”显式运行 1 个工况连接测试，只有许可证、四条光线、误差、`.zos` 与 SHA-256 全部通过才显示 PASS。
- 连接测试通过后，一键在真实 OpticStudio 中运行当前结果表；任务在后台串行执行，避免同时占用多个许可证。
- 下载包含批次快照、验证报告、结果 CSV 和 `.zos` 的可移交证据包；机器编译目录和原始日志不进入证据包或仓库。
- 直接打开版本化 PDF 报告、验证 JSON 和基准矩阵。

## 最简单的 OpticStudio 验证方式

1. 滚动到“04 Zemax 验证向导”。
2. 点击“自动检测 OpticStudio”。这一步不会启动 Zemax，许可证仍应显示“未测试”。
3. 检测通过后，勾选显式确认框，点击“运行 1 工况连接测试”。
4. 等待明确的 `PASS · 验证通过`。界面同时显示 OpticStudio 版本、通过工况数和最大边界误差。
5. PASS 后可点击“在 Zemax 运行当前结果表”；结束后下载可移交审计证据包。

网页不会在载入或只读检测时启动 OpticStudio。许可证状态只有真实 ZOS-API 运行返回有效时才显示“有效 · 已实测”。服务器仅监听 `127.0.0.1`，不向云端发送参数。

## 离线批次与命令行备用方式

结果表加载后，点击“生成 Zemax 审计批次”。解压下载的 ZIP 后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_zemax_batch.ps1 `
  -OpticStudioDir "C:\path\to\installed\OpticStudio"
```

只有输出目录中的 `verification_report.json` 同时满足 `verification_status = PASS`，才表示该批次经过真实 OpticStudio 验证。完整步骤、输出解释和故障排查见 [`../ZEMAX_CONNECTION_GUIDE.md`](../ZEMAX_CONNECTION_GUIDE.md)。

## 本地接口

- `GET /api/health`：健康状态。
- `GET /api/config`：公开且受约束的实验网格。
- `POST /api/calculate`：计算一个合法工况。
- `POST /api/sweep`：计算筛选矩阵或完整矩阵。
- `POST /api/range-sensitivity`：计算有效焦距、眼轴或瞳孔的三水平灵敏度。
- `POST /api/range-grid`：计算当前眼模型的三水平范围网格。
- `POST /api/zemax-batch`：重新计算传入工况并下载确定性的可审计 Zemax ZIP。
- `GET /api/zemax/preflight`：只读检测本机 Zemax 前置条件，不启动 OpticStudio。
- `POST /api/zemax/jobs`：在 `confirm=true` 时显式提交 1 工况连接测试或当前表格任务。
- `GET /api/zemax/jobs/<job-id>`：读取后台任务状态与脱敏验证摘要。
- `GET /api/zemax/jobs/<job-id>/evidence.zip`：下载不含构建目录和机器日志的可移交证据包。
- `GET /api/case.json?...`：下载一个工况。
- `GET /api/sweep.csv?...`：下载筛选矩阵或完整矩阵。
- `GET /api/range-sensitivity.csv?...` 与 `GET /api/range-grid.csv?...`：下载范围探索结果。

服务器默认只监听回环地址 `127.0.0.1`，不调用任何云服务。所有 API 输入都会重新检查眼模型、焦距、眼轴、瞳孔、物方需求和外镜屈光力是否属于版本化配置。

PPT 中给出的角膜曲率/屈光力和晶状体厚度/屈光力会在界面中作为来源参考显示，但不会被当作可独立追迹参数。PPT 缺少建立可信多表面模型所需的面间距、折射率、曲率和主平面数据；将这些数值直接叠加会产生不可辨识模型。
