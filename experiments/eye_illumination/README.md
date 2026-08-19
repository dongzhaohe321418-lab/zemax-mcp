# 小鸡与人眼 650 nm 固定焦距后极照明仿真

本目录把用户提供的《小鸡和人眼光学仿真参数》转换为可重复执行、可审计的光学实验。当前版本修正了旧模型“连续改变等效焦距以强制调焦”的假设：后极平面由已知眼轴固定，每种眼只取三个离散固定焦距，物距、瞳孔和焦距均作为独立输入。

**严格适用范围：**现有计算已经通过独立闭式复算和真实 OpticStudio Paraxial 一致性检查，但不能直接作为活体实验处方。252 个主工况的最大源边缘—瞳孔边缘角均超过项目设置的 10° 近轴筛查线，140 个工况的工作 F 数低于 4；程序因此把真实实验状态固定显示为 `NOT_READY`。必须完成真实曲面眼模型、real-ray/非序列辐射度验证、台架标定、ISO/IEC 光安全评价和伦理审批后才能放行。完整证据见 [`results/real_experiment_readiness.md`](results/real_experiment_readiness.md)。

## 专用实验程序

`app/` 是为本实验制作的本地交互程序。它不是静态报告：界面直接调用版本化的 `eye_model.py`。紧凑型 Web GUI 可在中文与 English 之间即时切换，固定基准模式严格复现三个焦距和 252 工况；独立的 PPT 范围探索模式允许手动改变有效焦距、眼轴、瞳孔、60–120 D 物方需求及外置凹透镜，并生成三水平灵敏度曲线和范围网格。程序不会为了满足物距而自动改变焦距。

范围文件 `app/range_parameters.json` 同时记录数值来源。小鸡眼轴 10.5–12.5 mm 来自 PPT；儿童与成人眼轴的 ±0.5 mm 是既有灵敏度假设，因为 PPT 只给出约 23.0 mm 和 23.6 mm。角膜和晶状体部件参数仅作为来源参考显示；缺少面间距和折射率时不将其伪装成可独立追迹变量。

第一次使用双击本目录的 `setup_web_gui.cmd`，它会建立私有 `.venv` 并自动启动；以后双击 `launch_web_gui.cmd`。也可以在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\app\launch_app.ps1
```

程序默认打开 `http://127.0.0.1:8765/`，只监听本机地址，不上传实验数据。交互计算不需要启动 OpticStudio；ZOS-API 仍用于版本化结果的独立交叉验证。

Web GUI 新增三步 Zemax 验证向导：只读自动发现安装、显式确认的 1 工况真实连接测试、清晰 PASS/FAIL 判定；测试通过后才解锁当前结果表的批量运行。结果表仍可生成确定性 Zemax 审计批次：相同输入会得到相同 batch ID 和 ZIP 哈希。批次内含服务器重新计算的输入、解析预期值、模型快照、通用 C# ZOS-API 执行器、独立校验器及一键 PowerShell 入口。它会为每个工况保存 `.zos`，记录 OpticStudio 版本、许可证状态、光线错误/渐晕和数值误差，最终生成 `verification_report.json`。详细安装、运行、人工抽查和故障排查见 [`ZEMAX_CONNECTION_GUIDE.md`](ZEMAX_CONNECTION_GUIDE.md)。

## 当前固定焦距

- 30–45 日龄小鸡：7.5、8.0、8.5 mm。
- 6 岁儿童：13.5、15.1、16.7 mm。
- 18 岁成人：12.8、14.75、16.7 mm。

原 PPT 只给出焦距范围，没有明确列出三组实测值，因此当前采用范围两端加算术中点。若存在指定实测值，修改 `config/experiment.json` 后即可完整重跑。

## 模型与实验矩阵

光线状态采用 `(y, nθ)`，固定后极约化距离为报告眼轴除以像方折射率 1.336。对固定焦距、固定物距和固定瞳孔，视网膜高度写为：

```text
y_retina = m_source * y_source + m_pupil * y_pupil
```

主矩阵包含 3 个眼模型 × 3 个固定焦距 × 4 个瞳孔 × 7 个物方需求，共 252 行。物方需求为 60、70、80、90、100、110、120 D，对应 16.67–8.33 mm 物距；这些数值不再被解释为调节需求。

每行输出两种尺寸：

- `geometric_min_source_diameter_mm`：外部光线 footprint 刚好达到目标边缘的理论最小值。
- `conservative_source_diameter_mm`：整个后极目标位于源像与瞳孔 footprint 全重叠平台内的近轴候选值，不是活体实验放行值。
- `maximum_source_pupil_ray_angle_deg`、`working_f_number`：近轴适用性筛查指标。

几何最小值可能为零，仅表示瞳孔离焦 footprint 已经达到目标边缘，不表示实际可以使用零面积光源。

## 一键复现

前提：Windows、Python 3.11+、OpticStudio 2024 R1 和有效 ZOS-API 许可证。

```powershell
python -m pip install -e ".[dev,analysis]"

powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\run_all.ps1 `
  -PythonPath "C:\path\to\python.exe" `
  -OpticStudioDir "C:\Program Files\Ansys Zemax OpticStudio 2024 R1.00"
```

该流程重新生成 252 行主扫描、600,000 光线蒙特卡洛案例、6 个固定焦距 `.zos` 系统、数值验证、已执行 Notebook 和自包含 HTML 报告。

中英文 LaTeX/PDF 报告一次构建：

```powershell
powershell -ExecutionPolicy Bypass -File experiments\eye_illumination\report\latex\build_report.ps1 `
  -PythonPath "C:\path\to\python.exe"
```

构建脚本分别连续编译三次，并检查两份报告的 A4 页面、对应字体嵌入、关键文本、图片数量、引用和版面越界。

## 当前关键结果

- 主扫描 252 行，结果中不再包含 `accommodation` 输出或“超过调节上限”的判定。
- 成人眼 `f=16.7 mm`、5 mm 瞳孔时，60 D 与 120 D 的保守光源直径分别为 10.389 mm 和 7.694 mm。
- 小鸡眼 `f=8.5 mm`、3.5 mm 瞳孔时，60 D 与 120 D 的保守光源直径分别为 9.008 mm 和 6.254 mm。
- 六个 OpticStudio 系统与解析 footprint 的最大边界误差为 `2.58e-11 µm`。
- 通用审计执行器已在 OpticStudio 24.1 对完整 252 工况全部验证通过，0 个失败，最大边界误差为 `3.02e-11 µm`；另含外置负镜的跨眼模型冒烟批次也通过。
- 中文 PDF 为 25 页，英文 PDF 为 22 页；两者均包含模型示意图、工作流、六张数据图、精确表格、验证、真实实验适用性审计和复现说明。

## 主要文件

- `config/experiment.json`：固定焦距、眼轴、后极、瞳孔与物距的唯一参数源。
- `eye_model.py`：固定参数 ABCD 映射和两种光源尺寸定义。
- `results/fixed_focal_source_sweep.csv`：252 行完整主矩阵。
- `results/headline_results.csv`：最大瞳孔下的 63 行查表结果。
- `zemax/ZosApiEyeValidation.cs`：六个固定焦距 OpticStudio 系统的自动生成与追迹。
- `zemax/ZosApiEyeBatch.cs`：读取应用批次的通用 OpticStudio Standalone 执行器。
- `zemax/run_zemax_batch.ps1`：编译、运行和校验任意应用批次的一键入口。
- `zemax/verify_zemax_results.py`：逐案例、逐文件哈希的独立 PASS/FAIL 校验器。
- `ZEMAX_CONNECTION_GUIDE.md`：应用连接 OpticStudio 的完整中文操作与审计指南。
- `../artifacts/eye-illumination-zemax-auditable-batch-v2/`：252 个 `.zos`、Zemax 结果、外镜冒烟批次、失败诊断和全部审计哈希。
- `../runs/eye-illumination-zemax-auditable-batch-v2.json`：本次批次接入里程碑的不可覆盖实验记录。
- `results/validation_report.json`：数值和 ZOS-API 自动验证。
- `../runs/eye-illumination-fixed-focal-60-120d-v3.json`：不可覆盖的本次实验记录、哈希与关键观察。
- `notebooks/eye_illumination_analysis.ipynb`：已执行的可复现 Notebook。
- `report/eye_illumination_report.html`：自包含技术报告。
- `report/latex/eye_illumination_experiment_report.pdf`：25 页中文宋体综合报告。
- `report/latex/eye_illumination_experiment_report_en.pdf`：22 页英文综合报告。

## 限制

当前结果是近轴几何覆盖和相对光线计数，不是绝对视网膜辐照度或眼组织安全结论。等效主平面、三个实际焦距、光源辐亮度、组织透射、像差和覆盖验收阈值仍需实测确认。范围模式可以加入外置近轴负镜，但这仍是等效面，不应冒充具有厚度、材料和像差的真实镜片。

真实实验还必须由本机构的光安全和伦理体系审核：眼科照明核对 ISO 15004-2:2024，非相干 LED/灯源核对 IEC 62471，激光核对 IEC 60825-1；小鸡实验取得动物伦理/IACUC 等效审批，人体实验取得 IRB/伦理审批与知情同意。仓库只提供可审计的计算和放行清单，不代替这些正式审批。
