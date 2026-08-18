"""Safe local OpticStudio discovery and explicit Web-GUI job execution."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Callable
import uuid
import zipfile

try:
    from .zemax_batch import BatchPackage, build_batch_package
except ImportError:  # Direct execution from server.py.
    from zemax_batch import BatchPackage, build_batch_package


REQUIRED_ASSEMBLIES = ("ZOSAPI.dll", "ZOSAPI_Interfaces.dll", "ZOSAPI_NetHelper.dll")
DEFAULT_TIMEOUT_SECONDS = 6 * 60 * 60


class ZemaxLocalError(ValueError):
    """Raised when a local Zemax action cannot be started safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compiler_path() -> Path | None:
    windows_dir = os.environ.get("WINDIR")
    if windows_dir:
        candidate = Path(windows_dir) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
        if candidate.is_file():
            return candidate.resolve()
    found = shutil.which("csc.exe") or shutil.which("csc")
    return Path(found).resolve() if found else None


def discover_opticstudio_installations() -> list[Path]:
    """Return installed OpticStudio directories without starting the application."""
    roots: list[Path] = []
    for variable in ("ProgramFiles", "ProgramW6432"):
        value = os.environ.get(variable)
        if value:
            root = Path(value)
            if root not in roots:
                roots.append(root)
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for candidate in sorted(root.glob("Ansys Zemax OpticStudio*"), reverse=True):
            if candidate.is_dir() and candidate not in found:
                found.append(candidate.resolve())
    return found


def zemax_preflight(opticstudio_dir: str | None = None) -> dict[str, Any]:
    """Inspect local prerequisites. This function never launches OpticStudio."""
    installations = discover_opticstudio_installations()
    requested = (opticstudio_dir or "").strip()
    if requested:
        selected = Path(requested).expanduser()
    else:
        environment_choice = os.environ.get("ZEMAX_OPTICSTUDIO_DIR", "").strip()
        selected = Path(environment_choice).expanduser() if environment_choice else (installations[0] if installations else None)

    selected_exists = bool(selected and selected.is_dir())
    selected_resolved = selected.resolve() if selected_exists and selected is not None else selected
    dlls = {
        name: bool(selected_resolved and (selected_resolved / name).is_file())
        for name in REQUIRED_ASSEMBLIES
    }
    compiler = _compiler_path()
    platform_supported = sys.platform == "win32"
    python_64bit = sys.maxsize > 2**32
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    ready = bool(
        platform_supported
        and python_64bit
        and compiler
        and powershell
        and selected_exists
        and all(dlls.values())
    )
    if ready:
        next_action = "可以运行 1 个工况的显式连接测试；尚未验证许可证。"
    elif not selected_exists:
        next_action = "请选择包含 ZOSAPI.dll 的 OpticStudio 安装目录。"
    elif not all(dlls.values()):
        next_action = "所选目录缺少一个或多个 ZOS-API 程序集。"
    else:
        next_action = "本机缺少受支持的 64 位 Windows、PowerShell 或 .NET C# 编译器。"
    return {
        "ready": ready,
        "platform_supported": platform_supported,
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "python_64bit": python_64bit,
        "compiler_found": compiler is not None,
        "powershell_found": powershell is not None,
        "selected_installation": str(selected_resolved) if selected_resolved else "",
        "discovered_installations": [str(path) for path in installations],
        "installation_exists": selected_exists,
        "api_dlls": dlls,
        "license_status": "NOT_TESTED",
        "next_action": next_action,
    }


def _default_runtime_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "EyeIlluminationLab" / "zemax_jobs"
    return Path(tempfile.gettempdir()) / "EyeIlluminationLab" / "zemax_jobs"


def _safe_archive(target_zip: Path, batch_dir: Path, results_dir: Path) -> None:
    """Create a portable evidence bundle while excluding builds and machine logs."""
    members: list[tuple[Path, str]] = []
    for path in sorted(batch_dir.rglob("*")):
        if path.is_file():
            members.append((path, f"input_batch/{path.relative_to(batch_dir).as_posix()}"))
    for path in sorted(results_dir.rglob("*")):
        if not path.is_file() or "_build" in path.parts or path.suffix.lower() == ".log":
            continue
        members.append((path, f"verified_results/{path.relative_to(results_dir).as_posix()}"))
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, name in members:
            archive.write(path, name)


CommandRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def _run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


class ZemaxJobManager:
    """Run at most one explicit local OpticStudio job at a time."""

    def __init__(
        self,
        runtime_root: Path | None = None,
        command_runner: CommandRunner | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.runtime_root = Path(runtime_root) if runtime_root else _default_runtime_root()
        self.command_runner = command_runner or _run_command
        self.timeout_seconds = timeout_seconds
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._active_job_id: str | None = None
        self._validated_installations: set[str] = set()

    def submit(
        self,
        rows: list[dict[str, Any]],
        opticstudio_dir: str,
        mode: str,
    ) -> dict[str, Any]:
        if mode not in {"connection_test", "table"}:
            raise ZemaxLocalError("mode must be connection_test or table")
        selected_rows = rows[:1] if mode == "connection_test" else rows
        if not selected_rows:
            raise ZemaxLocalError("at least one validated case is required")
        preflight = zemax_preflight(opticstudio_dir)
        if not preflight["ready"]:
            raise ZemaxLocalError(preflight["next_action"])
        installation_key = str(Path(preflight["selected_installation"])).casefold()
        with self._lock:
            if mode == "table" and installation_key not in self._validated_installations:
                raise ZemaxLocalError("请先让当前 OpticStudio 安装通过 1 工况连接测试。")
            if self._active_job_id is not None:
                active = self._jobs.get(self._active_job_id, {})
                if active.get("status") in {"queued", "running"}:
                    raise ZemaxLocalError("已有 Zemax 任务正在运行；许可证安全限制下请等待其结束。")
            package = build_batch_package(selected_rows)
            job_id = uuid.uuid4().hex
            job = {
                "job_id": job_id,
                "status": "queued",
                "stage": "WAITING",
                "message": "任务已排队，尚未启动 OpticStudio。",
                "mode": mode,
                "case_count": len(selected_rows),
                "batch_id": package.batch_id,
                "submitted_at_utc": _utc_now(),
                "started_at_utc": None,
                "finished_at_utc": None,
                "verification": None,
                "result_available": False,
                "result_zip": None,
            }
            self._jobs[job_id] = job
            self._active_job_id = job_id
        worker = threading.Thread(
            target=self._execute,
            args=(job_id, package, Path(preflight["selected_installation"])),
            name=f"zemax-job-{job_id[:8]}",
            daemon=True,
        )
        worker.start()
        return self.get(job_id)

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)

    def _execute(self, job_id: str, package: BatchPackage, opticstudio_dir: Path) -> None:
        job_root = self.runtime_root / job_id
        batch_dir = job_root / "batch"
        output_root = job_root / "runs"
        try:
            self._update(
                job_id,
                status="running",
                stage="PREPARING",
                message="正在冻结输入并准备可审计批次…",
                started_at_utc=_utc_now(),
            )
            batch_dir.mkdir(parents=True, exist_ok=False)
            output_root.mkdir(parents=True, exist_ok=False)
            package_path = job_root / package.filename
            package_path.write_bytes(package.content)
            with zipfile.ZipFile(package_path) as archive:
                archive.extractall(batch_dir)
            script = batch_dir / "scripts" / "run_zemax_batch.ps1"
            powershell = shutil.which("powershell.exe") or shutil.which("powershell")
            if not powershell:
                raise RuntimeError("PowerShell is unavailable")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-OpticStudioDir",
                str(opticstudio_dir),
                "-PythonPath",
                sys.executable,
                "-OutputRoot",
                str(output_root),
                "-RunId",
                job_id[:16],
            ]
            self._update(job_id, stage="OPTICSTUDIO", message="OpticStudio 正在建立系统并追迹光线…")
            completed = self.command_runner(command, self.timeout_seconds)
            reports = sorted(output_root.rglob("verification_report.json"))
            report = json.loads(reports[-1].read_text(encoding="utf-8")) if reports else None
            if report is None:
                raise RuntimeError("OpticStudio 任务未生成 verification_report.json")
            results_dir = reports[-1].parent
            result_zip = job_root / f"{package.batch_id}_verified_evidence.zip"
            _safe_archive(result_zip, batch_dir, results_dir)
            passed = completed.returncode == 0 and report.get("verification_status") == "PASS"
            public_verification = {
                "status": report.get("verification_status", "FAIL"),
                "opticstudio_versions": report.get("opticstudio_versions", []),
                "api_license_valid": report.get("api_license_valid", False),
                "expected_case_count": report.get("expected_case_count", len(reports)),
                "passed_case_count": report.get("passed_case_count", 0),
                "failed_case_count": report.get("failed_case_count", 0),
                "maximum_boundary_error_um": report.get("maximum_boundary_error_um"),
                "issues": report.get("issues", []),
            }
            if passed:
                with self._lock:
                    if self._jobs[job_id]["mode"] == "connection_test":
                        self._validated_installations.add(str(opticstudio_dir).casefold())
            self._update(
                job_id,
                status="pass" if passed else "fail",
                stage="COMPLETE",
                message=(
                    "真实 OpticStudio 运行与独立校验均通过。"
                    if passed
                    else "任务完成，但没有满足全部验证条件；请下载证据包查看报告。"
                ),
                finished_at_utc=_utc_now(),
                verification=public_verification,
                result_available=result_zip.is_file(),
                result_zip=str(result_zip),
            )
        except subprocess.TimeoutExpired:
            self._update(
                job_id,
                status="fail",
                stage="COMPLETE",
                message="OpticStudio 任务超时，未判定为通过。",
                finished_at_utc=_utc_now(),
            )
        except Exception as exc:  # Keep the local server alive and avoid exposing command output.
            self._update(
                job_id,
                status="fail",
                stage="COMPLETE",
                message=f"任务未完成：{type(exc).__name__}: {exc}",
                finished_at_utc=_utc_now(),
            )
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as exc:
                raise ZemaxLocalError("unknown Zemax job") from exc
            return {key: value for key, value in job.items() if key != "result_zip"}

    def result_path(self, job_id: str) -> Path:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as exc:
                raise ZemaxLocalError("unknown Zemax job") from exc
            path = job.get("result_zip")
        if not path or not Path(path).is_file():
            raise ZemaxLocalError("verified evidence is not available for this job")
        return Path(path)
