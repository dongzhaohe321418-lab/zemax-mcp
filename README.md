# Eye Illumination Web Lab for Zemax

**The main product in this repository is a local Web GUI for chick and human-eye posterior-pole illumination experiments.** It lets a user adjust the declared optical ranges, calculate reproducible source parameters, generate complete case tables, run guided OpticStudio verification, and download auditable evidence without working at a command line.

> **Real-experiment safety gate:** the current outputs are verified only within a first-order paraxial equivalent-eye model. They are not final source, power, or exposure settings for an animal or human eye. The application now reports edge-ray angle and working F-number diagnostics and keeps real-experiment status at `NOT_READY` until an anatomical real-ray model, calibrated radiometry, optical-safety assessment, and institutional ethics approval are supplied.

**MCP is a secondary, optional automation interface.** It remains available for constrained Codex or Claude Code workflows, but it is not required to use the experiment program.

## Start the program

On Windows, clone the private repository with Git LFS, then run the root launcher:

```powershell
git lfs install
git clone https://github.com/dongzhaohe321418-lab/zemax-mcp.git
cd zemax-mcp\experiments\eye_illumination
.\setup_web_gui.cmd
```

`setup_web_gui.cmd` creates a private local Python environment and opens the application. On later runs, double-click `launch_web_gui.cmd`. The GUI is served only at `http://127.0.0.1:8765/`; interactive ABCD calculations do not require OpticStudio and no experiment data is sent to a cloud service.

## What the program does

- Models 30–45 day chick, 6-year child, and 18-year adult effective eyes at 650 nm.
- Keeps posterior-pole geometry, object demand, pupil, and equivalent focal length as independent inputs.
- Uses three fixed focal lengths per eye in the validated baseline instead of continuously fitting focal length to object distance.
- Provides a separate PPT-range explorer for focal length, axial length, pupil, 60–120 D object demand, and constrained external concave lenses.
- Calculates individual cases, sensitivity sweeps, the full 252-case matrix, and three-level range grids.
- Draws the paraxial optical footprint and exports JSON, CSV, deterministic Zemax input batches, and verification evidence.
- Guides non-command-line users through **detect OpticStudio → verify one case → run the current table → download evidence**.

## Verified and auditable

The program distinguishes generated calculations from real OpticStudio results. Installation discovery never claims a valid license; only a completed ZOS-API run and independent verifier can display `PASS`.

| Verification scope | Result |
|---|---:|
| Web connection test on licensed OpticStudio 24.1 | 1 / 1 PASS |
| Web table batch with saved `.zos` systems | 21 / 21 PASS |
| Complete fixed-focal baseline | 252 / 252 PASS |
| Cross-model/external-lens smoke batch | 4 / 4 PASS |
| Repository test suite | 39 PASS |

Each transferable evidence package contains validated inputs, model/configuration snapshots, OpticStudio version and license status, ray/error/vignetting results, independent numeric checks, saved `.zos` systems, and SHA-256 hashes. Raw machine logs, credentials, and build directories are excluded.

## Experiment, report, and documentation

The completed 650 nm study includes a 252-row matrix, four pupils per eye, conservative and geometric source-size bounds, 600,000-ray Monte Carlo checks, an executed Notebook, CSV/JSON outputs, versioned OpticStudio evidence, and a 21-page Chinese LaTeX/PDF report with SimSun text.

- [Experiment overview](experiments/eye_illumination/README.md)
- [Web application guide](experiments/eye_illumination/app/README.md)
- [Zemax connection and audit guide](experiments/eye_illumination/ZEMAX_CONNECTION_GUIDE.md)
- [Real-experiment readiness audit](experiments/eye_illumination/results/real_experiment_readiness.md)
- [Chinese PDF report](experiments/eye_illumination/report/latex/eye_illumination_experiment_report.pdf)
- [Immutable experiment records](experiments/runs/)
- [Auditable binary artifacts](experiments/artifacts/)

## Optional MCP automation (secondary)

The repository also includes a safety-first, stdio-only MCP server for bounded sequential-mode operations from Codex, Claude Code, or another MCP host. A deterministic mock backend supports protocol testing without OpticStudio.

> The general-purpose MCP ZOS-API adapter deliberately stops after read-only runtime discovery until its object names and connection sequence are checked against the samples installed with the target OpticStudio release. The dedicated eye-experiment runner is live-verified, but that does not imply that the general MCP adapter is complete.

```text
MCP host (Codex / Claude Code)
             | stdio
             v
Python FastMCP server
             | typed, bounded operations
             v
Mock backend or guarded Windows ZOS-API adapter
```

## MCP safety model

- The server uses stdio and does not listen on a network port.
- It exposes a small typed tool set—no shell, arbitrary Python, arbitrary ZOS-API, or unrestricted filesystem tool.
- All file targets are resolved below the existing writable `ZEMAX_WORKSPACE`; absolute paths and traversal are rejected.
- Focus changes, optimization, saves, and standalone-session closure require an explicit `confirm=true` inside the tool.
- Save never overwrites an existing file.
- Tool calls are logged with status and exception type, but paths, tokens, credentials, and file contents are not logged.
- Simulation records are immutable and versioned. Git LFS stores large Zemax/binary artifacts.

## MCP prerequisites (secondary)

- Windows 10 or 11
- Python 3.11+
- Git and Git LFS
- For live mode: installed and licensed OpticStudio with ZOS-API samples
- `uv` (recommended) or pip/venv

Do not assume an installation path. In OpticStudio documentation or its installation folders, locate the Programming/ZOS-API Python samples and `ZOSAPI_NetHelper.dll`, then use those exact local paths. Python architecture must match the installed API runtime.

## MCP mock quick start

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

## MCP live ZOS-API preparation

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

## MCP host configuration (secondary)

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

## Recommended MCP optical workflow

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

## MCP tool limits

All length inputs are millimeters, wavelength inputs are micrometers, angles are degrees, and MTF frequencies are lp/mm. Lens diameter is 1–200 mm, center thickness 0.2–100 mm, curved radius magnitude 1–10,000 mm, wavelength 0.2–20 µm (up to 10), field magnitude up to 90° (up to 10), and MTF frequency 0–500 lp/mm (up to 20 samples). Optimization is bounded to 1–100 iterations and four whitelisted variables.

## MCP troubleshooting

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
experiments/eye_illumination/ primary local Web experiment program, model, report, and results
experiments/eye_illumination/app/ Web GUI, local server, setup scripts, and Zemax job manager
experiments/runs/        immutable JSON experiment records
experiments/artifacts/   Git LFS-backed designs and large results
experiments/templates/   record template
experiments/eye_illumination/zemax/ generic auditable ZOS-API eye batch runner and verifier
backend/                 secondary MCP backend protocol, mock, and guarded ZOS-API adapter
server.py                secondary FastMCP stdio tools
scripts/                 diagnostics and experiment recorder
tests/                   validation, path, and mock-physics tests
```
