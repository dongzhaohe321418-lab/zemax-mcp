from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "experiments" / "eye_illumination" / "app"
sys.path.insert(0, str(APP_DIR))

import zemax_local  # noqa: E402
from service import ExperimentService  # noqa: E402


def fake_ready_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    # Keep the fixture independent from run_all.ps1, which intentionally sets
    # this variable before exercising the licensed OpticStudio validation.
    monkeypatch.delenv("ZEMAX_OPTICSTUDIO_DIR", raising=False)
    install = tmp_path / "Ansys Zemax OpticStudio Test"
    install.mkdir()
    for name in zemax_local.REQUIRED_ASSEMBLIES:
        (install / name).write_bytes(b"test")
    compiler = tmp_path / "csc.exe"
    compiler.write_bytes(b"test")
    powershell = tmp_path / "powershell.exe"
    powershell.write_bytes(b"test")
    monkeypatch.setattr(zemax_local, "discover_opticstudio_installations", lambda: [install])
    monkeypatch.setattr(zemax_local, "_compiler_path", lambda: compiler)
    monkeypatch.setattr(zemax_local.sys, "platform", "win32")
    monkeypatch.setattr(zemax_local.shutil, "which", lambda name: str(powershell))
    return install


def test_preflight_is_read_only_and_reports_every_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install = fake_ready_environment(monkeypatch, tmp_path)
    result = zemax_local.zemax_preflight()
    assert result["ready"] is True
    assert result["selected_installation"] == str(install.resolve())
    assert result["api_dlls"] == {name: True for name in zemax_local.REQUIRED_ASSEMBLIES}
    assert result["license_status"] == "NOT_TESTED"
    assert "尚未验证许可证" in result["next_action"]


def test_preflight_rejects_a_directory_with_missing_api_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install = fake_ready_environment(monkeypatch, tmp_path)
    (install / "ZOSAPI.dll").unlink()
    result = zemax_local.zemax_preflight(str(install))
    assert result["ready"] is False
    assert result["api_dlls"]["ZOSAPI.dll"] is False
    assert "缺少" in result["next_action"]


def test_job_manager_runs_one_case_and_builds_sanitized_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install = fake_ready_environment(monkeypatch, tmp_path)

    def fake_runner(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        assert timeout == 30
        output_root = Path(command[command.index("-OutputRoot") + 1])
        run_dir = output_root / "fake-run"
        systems = run_dir / "systems"
        systems.mkdir(parents=True)
        (systems / "case.zos").write_bytes(b"zos")
        (run_dir / "runner.log").write_text("machine-specific path", encoding="utf-8")
        report = {
            "verification_status": "PASS",
            "opticstudio_versions": ["test-24.1"],
            "api_license_valid": True,
            "expected_case_count": 1,
            "passed_case_count": 1,
            "failed_case_count": 0,
            "maximum_boundary_error_um": 1e-12,
            "issues": [],
        }
        (run_dir / "verification_report.json").write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "PASS", "")

    manager = zemax_local.ZemaxJobManager(
        runtime_root=tmp_path / "runtime",
        command_runner=fake_runner,
        timeout_seconds=30,
    )
    rows = ExperimentService().sweep({"eye_id": "chick_30_45d", "focal_length_mm": 7.5})
    submitted = manager.submit(rows, str(install), "connection_test")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = manager.get(submitted["job_id"])
        if job["status"] not in {"queued", "running"}:
            break
        time.sleep(0.02)
    assert job["status"] == "pass"
    assert job["case_count"] == 1
    assert job["verification"]["api_license_valid"] is True
    assert job["result_available"] is True
    evidence = manager.result_path(job["job_id"])
    with zipfile.ZipFile(evidence) as archive:
        names = archive.namelist()
        assert "input_batch/manifest.json" in names
        assert "verified_results/verification_report.json" in names
        assert "verified_results/systems/case.zos" in names
        assert not any(name.endswith(".log") or "_build" in name for name in names)


def test_job_start_rejects_without_ready_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(zemax_local, "discover_opticstudio_installations", lambda: [])
    manager = zemax_local.ZemaxJobManager(runtime_root=tmp_path / "runtime")
    row = ExperimentService().sweep()[0]
    with pytest.raises(zemax_local.ZemaxLocalError, match="请选择"):
        manager.submit([row], str(tmp_path / "missing"), "connection_test")


def test_table_job_requires_a_passed_connection_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    install = fake_ready_environment(monkeypatch, tmp_path)
    manager = zemax_local.ZemaxJobManager(runtime_root=tmp_path / "runtime")
    row = ExperimentService().sweep()[0]
    with pytest.raises(zemax_local.ZemaxLocalError, match="先让当前 OpticStudio"):
        manager.submit([row], str(install), "table")
