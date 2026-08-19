# Eye Illumination Web Lab

用于小鸡、儿童和成人眼后极照明参数研究的本地 Web 程序，支持参数计算、批量扫描、报告导出和 Ansys Zemax OpticStudio 验证。

**程序是本仓库的主体；MCP 只是可选的二级自动化接口。**

> [!WARNING]
> 当前结果只在一阶近轴等效眼模型内通过验证。所有尺寸都是后续建模与台架实验的候选值，不是动物或人体眼部照明的最终功率、尺寸或曝光处方。程序会保持真实实验状态为 `NOT_READY`，直到真实曲面模型、辐射度标定、光安全评价和伦理审批全部完成。

## 1. Windows 三分钟启动

### 需要安装

- Windows 10 或 11（64 位）
- Python 3.11 或更高版本（64 位）
- Git 和 [Git LFS](https://git-lfs.com/)
- 可访问 GitHub 的网络连接（仓库为公开仓库，克隆无需登录）

交互计算不需要 OpticStudio。只有执行 Zemax 验证时才需要已安装并授权的 OpticStudio。

### 第一次使用

在 PowerShell 中运行：

```powershell
git lfs install
git clone https://github.com/dongzhaohe321418-lab/zemax-mcp.git
cd zemax-mcp
git lfs pull
.\experiments\eye_illumination\setup_web_gui.cmd
```

安装脚本会：

1. 在程序目录创建独立的 `.venv`；
2. 安装固定范围的 NumPy 依赖；
3. 检查 Python 与 NumPy；
4. 启动本地服务器并打开浏览器。

本仓库为公开仓库，克隆和 `git lfs pull` 无需 GitHub 登录。如果克隆失败，请先检查能否访问 `https://github.com`，并确认 Git LFS 已正确安装。

### 以后启动

双击：

```text
experiments\eye_illumination\launch_web_gui.cmd
```

也可以在 PowerShell 中运行：

```powershell
.\experiments\eye_illumination\launch_web_gui.cmd
```

程序地址是 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)。右上角可在中文与 English 之间即时切换，动态计算、图表、Zemax 向导和 PDF 报告链接会同步切换。服务器只监听本机回环地址，不把实验参数发送到云端。关闭启动窗口或按 `Ctrl+C` 即可停止。

## 2. 最简单的使用流程

1. 选择“固定三焦距基准”或“PPT 参数范围探索”。
2. 选择眼模型、固定焦距、瞳孔和 60–120 D 物方需求。
3. 点击“运行当前工况”，查看候选光源尺寸、边缘角和工作 F 数。
4. 按需下载当前 JSON、结果 CSV 或全部 252 工况。
5. 需要 Zemax 复核时，继续使用页面底部的三步验证向导。

程序不会根据物距自动改变眼球等效焦距。固定焦距、眼轴、瞳孔、物距和可选外置负镜始终是相互独立的输入。

## 3. 在 OpticStudio 中验证

### 前置条件

- Windows 64 位 Python 3.11+
- 已安装并授权的 Ansys Zemax OpticStudio
- 安装目录中存在 `ZOSAPI.dll`、`ZOSAPI_Interfaces.dll` 和 `ZOSAPI_NetHelper.dll`
- Windows .NET Framework 64 位 C# 编译器

### 网页内三步验证

1. 滚动到“04 Zemax 验证向导”。
2. 点击“自动检测 OpticStudio”。这一步只读，不启动 Zemax，也不声称许可证有效。
3. 勾选确认框，点击“运行 1 工况连接测试”。
4. 等待 `PARAXIAL PASS · 一致性通过`。
5. 连接测试通过后，再运行当前结果表并下载证据 ZIP。

证据包包含输入、模型快照、OpticStudio 版本、许可证状态、结果 CSV、保存的 `.zos` 系统、独立校验报告和 SHA-256；不包含机器构建目录或原始日志。

`PARAXIAL PASS` 只证明解析 ABCD 模型与理想 OpticStudio Paraxial 面一致，不代表真实眼、绝对辐照度、光安全或生物学结果通过。完整步骤见[《Zemax 连接与审计指南》](experiments/eye_illumination/ZEMAX_CONNECTION_GUIDE.md)。

## 4. 当前验证状态

| 项目 | 当前结果 |
|---|---:|
| 固定焦距主矩阵 | 252 行，0 重复，0 数值缺失 |
| 独立闭式复算最大光源直径差异 | `4.59e-09 mm` |
| OpticStudio 24.1 六工况交叉验证 | 6 / 6 PASS |
| 六工况最大边界误差 | `2.58e-11 µm` |
| 最新网页连接测试 | 1 / 1 PASS |
| 完整可审计基准批次 | 252 / 252 PASS |
| 自动化测试 | 45 / 45 PASS |
| 中文 PDF | 25 页，A4，SimSun/宋体已嵌入 |
| English PDF | 22 页，A4，Times New Roman 已嵌入 |
| 真实实验状态 | `NOT_READY` |

模型适用性审计发现：252 个工况的最大源边缘—瞳孔边缘角均为 15.02°–37.59°，全部触发项目设置的 10° 真实光线复核线；140 个工况的工作 F 数低于 4。因此，当前结果适合用于候选机械空间、参数筛选和下一阶段真实模型设计，不能直接作为活体曝光设置。

## 5. 结果、报告与证据

| 内容 | 文件 |
|---|---|
| 实验与模型说明 | [experiments/eye_illumination/README.md](experiments/eye_illumination/README.md) |
| Web 程序操作说明 | [experiments/eye_illumination/app/README.md](experiments/eye_illumination/app/README.md) |
| Zemax 连接与审计 | [experiments/eye_illumination/ZEMAX_CONNECTION_GUIDE.md](experiments/eye_illumination/ZEMAX_CONNECTION_GUIDE.md) |
| 真实实验适用性审计 | [real_experiment_readiness.md](experiments/eye_illumination/results/real_experiment_readiness.md) |
| 综合 HTML 报告 | [eye_illumination_report.html](experiments/eye_illumination/report/eye_illumination_report.html) |
| 25 页中文 PDF | [eye_illumination_experiment_report.pdf](experiments/eye_illumination/report/latex/eye_illumination_experiment_report.pdf) |
| 22-page English PDF | [eye_illumination_experiment_report_en.pdf](experiments/eye_illumination/report/latex/eye_illumination_experiment_report_en.pdf) |
| 252 工况 CSV | [fixed_focal_source_sweep.csv](experiments/eye_illumination/results/fixed_focal_source_sweep.csv) |
| 已执行 Notebook | [eye_illumination_analysis.ipynb](experiments/eye_illumination/notebooks/eye_illumination_analysis.ipynb) |
| 不可变实验记录 | [experiments/runs/](experiments/runs/) |
| Zemax 与二进制证据 | [experiments/artifacts/](experiments/artifacts/) |

## 6. 版本兼容性

- Web 计算程序支持 Windows 上的 Python 3.11+，不依赖特定 OpticStudio 版本。
- ZOS-API 实机证据来自 OpticStudio `24.1.0`。
- 其他 OpticStudio 版本如果仍提供上述三个 ZOS-API DLL，通常可以由程序自动发现，但必须先通过“1 工况连接测试”，不能沿用旧版本的许可证或数值结论。
- 程序不会把 DLL 存在等同于许可证有效；许可证状态只由真实 ZOS-API 运行确认。

## 7. 常见问题

| 现象 | 处理方法 |
|---|---|
| 公开仓库无法克隆 | 检查 GitHub 网络连接，运行 `git lfs install`，再重新克隆；只读使用无需 `gh auth login`。 |
| 提示找不到 Python | 安装 64 位 Python 3.11+，或在仓库根目录执行 `powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\setup_local.ps1 -PythonPath "C:\path\to\python.exe"`。 |
| 浏览器没有自动打开 | 保持启动窗口开启，手动访问 `http://127.0.0.1:8765/`。 |
| 8765 端口已占用 | 在仓库根目录执行 `powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1 -Port 8766`，然后访问对应端口。 |
| NumPy 缺失 | 重新运行 `setup_web_gui.cmd`。 |
| 未检测到 OpticStudio | 在向导中选择包含三个 ZOS-API DLL 的实际安装目录。 |
| 显示 `PARAXIAL PASS` 但仍是 `NOT_READY` | 这是预期行为；前者是模型一致性，后者是真实实验放行状态。 |
| Zemax 任务失败 | 下载/查看失败摘要，并按连接指南检查版本、许可证、DLL 和 C# 编译器。 |

## 8. 开发与完整复现

普通用户不需要执行本节。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,analysis]"
python -m pytest -q
```

包含许可版 OpticStudio、Notebook 和 HTML 报告的完整工作流：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\run_all.ps1 `
  -OpticStudioDir "C:\path\to\installed\OpticStudio"
```

中英文 LaTeX/PDF 一次构建：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\report\latex\build_report.ps1
```

脚本会生成并自检两份报告：25 页中文宋体版和 22 页英文版，同时检查 A4 页面、字体嵌入、关键文字、图片数量、引用和版面越界。

完整工作流会启动许可版 OpticStudio；运行前请保存其他 OpticStudio 工作并确认许可证可用。

## 9. 可选 MCP 自动化

MCP 不是运行本实验程序的必要条件。需要从 Codex、Claude Code 或其他 MCP 主机调用受限光学工具时，请阅读[《可选 MCP 使用指南》](MCP_GUIDE.md)。

## 10. 仓库结构

```text
experiments/eye_illumination/      主程序、模型、结果、报告和 Zemax runner
experiments/eye_illumination/app/  本地 Web GUI 与三步 Zemax 验证向导
experiments/runs/                  不可覆盖的实验记录
experiments/artifacts/             Git LFS 管理的 Zemax/二进制证据
tests/                             模型、Web、批次和安全边界测试
backend/ + server.py               可选 MCP 接口
scripts/                           诊断和实验记录工具
```

每个重要实验里程碑都必须新增不可变记录、保存相关证据、运行测试并推送 GitHub；详细规则见 [AGENTS.md](AGENTS.md)。
