# Zemax MCP

A safety-first, stdio-only MCP server that lets Codex, Claude Code, or another MCP host drive constrained Ansys Zemax OpticStudio sequential-mode workflows. The project includes a deterministic mock backend so validation and protocol work can proceed without an OpticStudio installation.

> Current status: the mock backend is implemented and testable. The ZOS-API adapter deliberately stops after read-only runtime discovery until its object names and connection sequence are checked against the samples installed with the target OpticStudio release. It has **not** been verified against a live licensed OpticStudio instance.

```text
MCP host (Codex / Claude Code)
             | stdio
             v
Python FastMCP server
             | typed, bounded operations
             v
Mock backend or Windows ZOS-API adapter
             |
             v
Ansys Zemax OpticStudio (sequential mode)
```

## Safety model

- The server uses stdio and does not listen on a network port.
- It exposes a small typed tool set—no shell, arbitrary Python, arbitrary ZOS-API, or unrestricted filesystem tool.
- All file targets are resolved below the existing writable `ZEMAX_WORKSPACE`; absolute paths and traversal are rejected.
- Focus changes, optimization, saves, and standalone-session closure require an explicit `confirm=true` inside the tool.
- Save never overwrites an existing file.
- Tool calls are logged with status and exception type, but paths, tokens, credentials, and file contents are not logged.
- Simulation records are immutable and versioned. Git LFS stores large Zemax/binary artifacts.

## Windows prerequisites

- Windows 10 or 11
- Python 3.11+
- Git and Git LFS
- For live mode: installed and licensed OpticStudio with ZOS-API samples
- `uv` (recommended) or pip/venv

Do not assume an installation path. In OpticStudio documentation or its installation folders, locate the Programming/ZOS-API Python samples and `ZOSAPI_NetHelper.dll`, then use those exact local paths. Python architecture must match the installed API runtime.

## Mock quick start

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

Pip alternative:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:ZEMAX_WORKSPACE = "C:\zemax-workspace"
$env:ZEMAX_BACKEND = "mock"
python server.py
```

For interactive MCP inspection:

```powershell
uv run mcp dev server.py
```

Expected `zemax_health` behavior in mock mode: `connected` is true, `backend` is `mock`, the resolved workspace is shown, no OpticStudio version is claimed, and analysis/optimization capabilities are marked `estimated`.

## Live ZOS-API preparation

Install the optional bridge, run diagnostics, and only then start the server:

```powershell
uv sync --extra zosapi --extra dev
$env:ZEMAX_WORKSPACE = "C:\path\to\approved-workspace"
$env:ZEMAX_BACKEND = "zosapi"
$env:ZEMAX_CONNECT_MODE = "extension"
$env:ZEMAX_ZOSAPI_NETHELPER_DLL = "C:\path\from\installed\samples\ZOSAPI_NetHelper.dll"
uv run python scripts\diagnose_zosapi.py
uv run python server.py
```

`extension` mode must never close a user-owned OpticStudio process. `standalone` closure still requires confirmation. Adapt `backend/zosapi_backend.py` only after comparing it to the local, version-matched Python samples. DLL load, license, and connection errors must remain diagnostic rather than being converted to apparent success.

## MCP host configuration

Claude Code template (replace every placeholder):

```powershell
claude mcp add --transport stdio zemax-opticstudio `
  --env ZEMAX_BACKEND=zosapi `
  --env ZEMAX_WORKSPACE="C:\path\to\approved-workspace" `
  --env ZEMAX_CONNECT_MODE=extension `
  -- "C:\path\to\python.exe" "C:\path\to\zemax-mcp\server.py"
```

Codex configuration entry points vary by client version. A standard stdio definition needs `command`, `args`, and `env`:

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

## Recommended optical workflow

Ask for missing wavelength band, aperture or F-number, object condition, fields, sensor size, allowed materials, and optimization objective. Then:

1. Call `new_sequential_design`, `create_singlet`, and `configure_system`.
2. Call `quick_focus_preview` and `paraxial_summary`.
3. Review EFL/BFL and assumptions; only then call `apply_quick_focus(confirm=true)`.
4. Call `spot_diagram` and `mtf`, recognizing singlet spherical, chromatic, and off-axis aberrations.
5. Call `preview_optimization`; call `run_optimization(..., confirm=true)` only after reviewing variables, bounds, and cost.
6. Call `preview_save_design`; call `save_design(..., confirm=true)` only after reviewing the new path.

Example request: “Using N-BK7, model a 25 mm diameter plano-convex singlet targeting 75 mm EFL at Fraunhofer F/d/C wavelengths, object at infinity, 10 mm entrance pupil, and fields 0° and 5°. Preview focus before changing it, then report paraxial data, spot sizes, and MTF.”

## Recording every experimental milestone

The repository is the experiment system of record. Copy `experiments/templates/experiment.json`, fill it with exact inputs and numeric outputs, then create a non-overwritable record:

```powershell
python scripts\record_experiment.py exp-001-bk7-focus C:\path\to\completed-record.json
```

Place referenced `.ZOS`, `.ZMX`, plots, arrays, or archives below `experiments/artifacts/<experiment-id>/`, update `EXPERIMENTS.md`, run tests, inspect the diff, commit the milestone, and push. The included `AGENTS.md` tells future Codex sessions to follow this process after every meaningful run. Never commit credentials, license details, user-specific paths, or sensitive logs.

## Tool limits

All length inputs are millimeters, wavelength inputs are micrometers, angles are degrees, and MTF frequencies are lp/mm. Lens diameter is 1–200 mm, center thickness 0.2–100 mm, curved radius magnitude 1–10,000 mm, wavelength 0.2–20 µm (up to 10), field magnitude up to 90° (up to 10), and MTF frequency 0–500 lp/mm (up to 20 samples). Optimization is bounded to 1–100 iterations and four whitelisted variables.

## Troubleshooting

| Symptom | Action |
|---|---|
| `ZEMAX_WORKSPACE` error | Create the intended directory explicitly, verify it is writable, then set the variable. |
| `pythonnet` unavailable | Install `.[zosapi]` using the same Python architecture as OpticStudio. |
| NetHelper load failure | Use the DLL path from the installed, version-matched ZOS-API sample. |
| License/connection failure | Open OpticStudio, verify the license, connection mode, and sample code behavior. |
| Glass rejected in mock mode | Use `N-BK7`, `N-SF11`, or `F_SILICA`; live catalogs require ZOS-API verification. |
| Save refused | Use a relative `.ZOS` path below the workspace, an existing parent directory, and a new filename. |
| Optimization unsupported | Use a bounded manual parameter sweep; no backend may fabricate success. |

## Repository layout

```text
backend/                 backend protocol, mock, and guarded ZOS-API adapter
experiments/runs/        immutable JSON experiment records
experiments/artifacts/   Git LFS-backed designs and large results
experiments/templates/   record template
scripts/                 diagnostics and experiment recorder
tests/                   validation, path, and mock-physics tests
server.py                FastMCP stdio tools
```
