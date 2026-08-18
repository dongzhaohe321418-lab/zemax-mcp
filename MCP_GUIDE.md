# 可选 MCP 使用指南

本指南只适用于需要从 Codex、Claude Code 或其他 MCP 主机调用受限 Zemax 工具的用户。后极照明 Web 程序不需要 MCP；普通实验用户应从根目录 [README](README.md) 开始。

## 设计边界

- MCP 服务器使用 `stdio`，不监听网络端口。
- 只公开固定、带类型和范围检查的工具，不提供 shell、任意 Python 或任意 ZOS-API 调用。
- 所有文件目标必须位于已存在且可写的 `ZEMAX_WORKSPACE` 下。
- 调焦、优化、保存和关闭 standalone 会话需要显式 `confirm=true`。
- 保存操作不覆盖已有文件。
- mock 后端用于协议和工作流测试，不声称使用过 OpticStudio。
- 通用 ZOS-API adapter 必须与目标版本自带样例核对后才能用于 live 模式。

## 前置条件

- Windows 10 或 11
- Python 3.11+
- Git 与 Git LFS
- `uv`（推荐）或 pip/venv
- live 模式：已安装并授权的 OpticStudio，以及版本匹配的 ZOS-API 样例和 DLL

不要猜测 OpticStudio 安装路径。请从本机安装目录或 Programming/ZOS-API 样例中找到 `ZOSAPI_NetHelper.dll` 的真实路径。

## Mock 模式快速启动

```powershell
git lfs install
New-Item -ItemType Directory C:\zemax-workspace
Copy-Item .env.example .env
$env:ZEMAX_WORKSPACE = "C:\zemax-workspace"
$env:ZEMAX_BACKEND = "mock"
uv sync --extra dev
uv run pytest -q
uv run python server.py
```

pip 替代方式：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:ZEMAX_WORKSPACE = "C:\zemax-workspace"
$env:ZEMAX_BACKEND = "mock"
python server.py
```

mock 模式的 `zemax_health` 应显示：`connected=true`、`backend=mock`，且不声明 OpticStudio 版本；分析和优化能力会明确标为估算。

## Live ZOS-API 准备

```powershell
uv sync --extra zosapi --extra dev
$env:ZEMAX_WORKSPACE = "C:\path\to\approved-workspace"
$env:ZEMAX_BACKEND = "zosapi"
$env:ZEMAX_CONNECT_MODE = "extension"
$env:ZEMAX_ZOSAPI_NETHELPER_DLL = "C:\path\from\installed\samples\ZOSAPI_NetHelper.dll"
uv run python scripts\diagnose_zosapi.py
uv run python server.py
```

只有 `diagnose_zosapi.py` 明确通过后才能启动 live 模式。DLL 加载、许可证或连接失败必须保留为失败，不能转换成表面成功。

`extension` 模式连接用户拥有的 OpticStudio 进程，绝不能由 MCP 关闭；`standalone` 会话的关闭仍需要显式确认。

## Claude Code 配置示例

替换全部占位符：

```powershell
claude mcp add --transport stdio zemax-opticstudio `
  --env ZEMAX_BACKEND=zosapi `
  --env ZEMAX_WORKSPACE="C:\path\to\approved-workspace" `
  --env ZEMAX_CONNECT_MODE=extension `
  -- "C:\path\to\python.exe" "C:\path\to\zemax-mcp\server.py"
```

## 通用 stdio 配置示例

Codex 或其他 MCP 客户端通常需要 `command`、`args` 和 `env`：

```json
{
  "mcpServers": {
    "zemax-opticstudio": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["C:\\path\\to\\zemax-mcp\\server.py"],
      "env": {
        "ZEMAX_BACKEND": "zosapi",
        "ZEMAX_WORKSPACE": "C:\\path\\to\\approved-workspace",
        "ZEMAX_CONNECT_MODE": "extension"
      }
    }
  }
}
```

具体配置文件位置取决于 MCP 客户端版本，请以该客户端当前文档为准。

## 推荐工作流

1. 明确波长、孔径/F 数、物距、视场、传感器尺寸、材料限制和优化目标。
2. 调用 `new_sequential_design`、`create_singlet` 和 `configure_system`。
3. 调用 `quick_focus_preview` 与 `paraxial_summary`。
4. 审查假设和 EFL/BFL 后，再调用 `apply_quick_focus(confirm=true)`。
5. 查看 spot diagram 与 MTF；不要忽略球差、色差和离轴像差。
6. 先调用 `preview_optimization`，确认变量和边界后再运行优化。
7. 先调用 `preview_save_design`，确认新路径后再保存。

## 单位与范围

- 长度：mm
- 波长：µm
- 角度：degree
- MTF 频率：lp/mm
- 镜片直径：1–200 mm
- 中心厚度：0.2–100 mm
- 曲率半径绝对值：1–10,000 mm
- 波长：0.2–20 µm，最多 10 个
- 视场绝对值：不超过 90°，最多 10 个
- MTF：0–500 lp/mm，最多 20 个采样
- 优化：1–100 次迭代，最多四个白名单变量

## 故障排查

| 现象 | 处理方法 |
|---|---|
| `ZEMAX_WORKSPACE` 错误 | 显式创建目标目录、确认可写，再设置环境变量。 |
| `pythonnet` 不可用 | 用与 OpticStudio API 架构一致的 Python 安装 `.[zosapi]`。 |
| NetHelper 加载失败 | 使用本机目标版本样例中的真实 DLL 路径。 |
| 许可证/连接失败 | 打开 OpticStudio，检查许可证、连接模式和版本匹配的样例代码。 |
| mock 模式玻璃被拒绝 | 使用 `N-BK7`、`N-SF11` 或 `F_SILICA`；live 目录需要真实 ZOS-API 验证。 |
| 保存被拒绝 | 使用工作区内的相对 `.ZOS` 路径、已有父目录和未占用的新文件名。 |
| 后端不支持优化 | 改用有界参数扫描，禁止伪造成功。 |

## 实验记录

每个重要 MCP 仿真都必须使用 `scripts/record_experiment.py` 创建不可覆盖的记录，并把 `.zos`、图表或数组放入 `experiments/artifacts/<experiment-id>/`。不要提交凭据、许可证详情、用户专用路径或原始机器日志。
