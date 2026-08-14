# 小鸡与人眼 650 nm 全视网膜照明仿真

本目录把用户提供的《小鸡和人眼光学仿真参数》转换为可重复执行、可审计的光学实验。它包含独立近轴模型、参数扫描、蒙特卡洛照度均匀性评估、真实 Ansys Zemax OpticStudio 24.1 ZOS-API 光线追迹、自动测试、执行完成的 Jupyter Notebook、自包含 HTML 技术报告，以及 30 页中文宋体 LaTeX/PDF 综合实验报告。

## 已完成的建模

三个有效眼模型分别表示 30–45 日龄小鸡、6 岁儿童和 18 岁成人。模型采用光线状态 `(y, nθ)` 与 ABCD 矩阵：

- 空间传播：`[[1, d/n], [0, 1]]`
- 薄透镜：`[[1, 0], [-F, 1]]`
- 聚焦条件：从光源平面到视网膜的系统矩阵满足 `B = 0`
- 视网膜覆盖：聚焦成像圆盘直径不小于 PPT 指定的后极部目标直径
- 离焦模糊：从最大边缘光线的视网膜交点包络计算几何模糊斑

调节通过改变眼的有效屈光力实现，视网膜位置固定。负外置镜片通过顶点距传播矩阵与眼透镜串联。物距、离焦、瞳孔、眼轴、调节上限和外置镜片均纳入扫参。

## 一键复现

前提：Windows、Python 3.11+、OpticStudio 与有效 ZOS-API 许可证。先安装依赖：

```powershell
python -m pip install -e ".[dev,analysis]"
```

然后在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\run_all.ps1 `
  -PythonPath "C:\path\to\python.exe" `
  -OpticStudioDir "C:\Program Files\Ansys Zemax OpticStudio 2024 R1.00"
```

脚本依次重建独立模型结果和图、编译并运行 64 位 ZOS-API 验证器、验证数值、重建并执行 Notebook、运行全部测试、生成规范化报告数据和便携 HTML 报告。`.build/` 仅用于临时编译产物，不进入版本控制。

## LaTeX/PDF 综合报告

报告正文、表格和中文数据图均由版本化 CSV/JSON 结果生成，包含等效眼与外置负镜片光路图、端到端可复现工作流图、全部实验细节、结果、限制和下一阶段计划。Windows 上安装 MiKTeX/XeLaTeX 与分析依赖后，在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\report\latex\build_report.ps1 `
  -PythonPath "C:\path\to\python.exe"
```

构建脚本会重新生成表格宏和五张中文图，连续编译三次，并自动检查 A4 页面、宋体嵌入、图片数量、关键文本、稀疏页、未解析引用和版面越界。最终 PDF 位于 `report/latex/eye_illumination_experiment_report.pdf`，机器审计结果位于 `report/latex/qa_report.json`。

## 主要结果

- 物方需求主扫描为 60、70、80、90、100、110、120 D。成人与儿童所需圆形光源直径从 60 D 的约 5.99 mm 降至 120 D 的约 2.99 mm；小鸡从约 5.95 mm 降至约 2.98 mm。
- 无穷远条件下所需完整角直径为小鸡 20.46°、儿童与成人 20.59°。
- 全部 60–120 D 请求案例均超过小鸡、儿童和成人模型的给定调节上限；这些结果是几何覆盖尺寸，不是生理可调焦结论。
- 外置镜片保留为独立 10 D 参考扫描：成人眼加 -10 D 外置镜片时需要 17.00 D 调节，仍可行；-15 D 与 -20 D 分别需要 20.03 D、22.79 D，不可行。90–120 D 人眼物距短于暂定 12 mm 顶点距，因此不生成物理顺序无效的组合。
- 成人 5 mm 瞳孔在 10 D 离焦时几何模糊斑直径为 0.835 mm；小鸡 3.5 mm 瞳孔对应 0.294 mm。
- 聚焦成人 10 D 蒙特卡洛案例的目标捕获比例为 1.000，`p10/mean` 均匀性为 0.846；采用覆盖 10 D 离焦的保守光源后，捕获比例为 0.771，`p10/mean` 为 0.831。
- 5 个聚焦 ZOS-API 案例的最大视网膜边缘误差为 4.44×10⁻¹³ µm；故意不调焦案例的预测与 ZOS 展宽均为 0.82665 mm。

## 目录与数据血缘

- `source/`：用户提供的原始 PPT（未修改）。
- `config/experiment.json`：唯一实验参数源与假设清单。
- `eye_model.py`：矩阵光学、调节、尺寸和离焦计算核心。
- `run_experiment.py`：全部扫参、蒙特卡洛与静态图。
- `zemax/ZosApiEyeValidation.cs`：真实 OpticStudio 系统创建与批量光线追迹。
- `results/`：CSV、JSON、`.zos` 与 `.ZDA` 完整结果。
- `results/external_lens_reference.csv`：与 60–120 D 主扫描分离的 10 D 外置镜片参考结果。
- `notebooks/eye_illumination_analysis.ipynb`：含输出的可执行分析 Notebook。
- `report/artifact.json`：报告的规范化、带来源数据。
- `report/eye_illumination_report.html`：自包含技术报告。
- `report/latex/`：中文宋体 LaTeX 源码、五张数据图、TikZ 示意图、30 页 PDF 与自动 QA。
- `validate_results.py` 与 `tests/test_eye_illumination_model.py`：自动数值验证和单元测试。

## 限制

当前成果是几何光学和相对照度的第一阶段工程模型。PPT 未给出绝对光功率、曝光时间、光谱带宽、组织透射、曲率、折射率、像差、散射和眼球转动包络，因此不能据此声称绝对视网膜辐照度或眼组织安全。PPT 第 5 页的“15 D”按上下文暂解释为 -15 D；小鸡 5 mm 和人眼 12 mm 的外置镜片顶点距为待实测假设。
