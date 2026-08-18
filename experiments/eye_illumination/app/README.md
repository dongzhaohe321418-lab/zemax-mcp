# 固定焦距后极照明实验程序

这是 `eye-illumination-fixed-focal-60-120d-v3` 的本地交互应用。程序直接调用上级目录的 `eye_model.py` 和 `config/experiment.json`，不会复制或重新实现光学公式。

## 启动

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

程序要求 Python 3.11+ 和 NumPy；仓库开发环境可以通过 `python -m pip install -e ".[dev,analysis]"` 安装完整依赖。

## 功能

- 从三个眼模型中选择小鸡、6 岁儿童或 18 岁成人。
- 焦距下拉框只暴露对应模型的三个固定值，不接受连续拟合值。
- 物方需求固定为 60–120 D，步长 10 D。
- 已知眼轴、后极目标和像方折射率在界面中只读显示。
- 即时输出几何最小和推荐全重叠光源尺寸。
- 绘制光源—等效透镜—固定后极的 SVG 光路示意。
- 比较三个固定焦距随物方需求变化的曲线。
- 生成 21 行当前对比或完整 252 行矩阵。
- 将当前工况导出为 JSON，将结果矩阵导出为带 UTF-8 BOM 的 CSV。
- 直接打开版本化 PDF 报告、验证 JSON 和基准矩阵。

## 本地接口

- `GET /api/health`：健康状态。
- `GET /api/config`：公开且受约束的实验网格。
- `POST /api/calculate`：计算一个合法工况。
- `POST /api/sweep`：计算筛选矩阵或完整矩阵。
- `GET /api/case.json?...`：下载一个工况。
- `GET /api/sweep.csv?...`：下载筛选矩阵或完整矩阵。

服务器默认只监听回环地址 `127.0.0.1`，不调用任何云服务。所有 API 输入都会重新检查眼模型、固定焦距、瞳孔和物方需求是否属于版本化配置。
