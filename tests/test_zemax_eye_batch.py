from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "experiments" / "eye_illumination" / "app"
ZEMAX_DIR = APP_DIR.parent / "zemax"
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ZEMAX_DIR))

from service import ExperimentService, RequestError  # noqa: E402
from verify_zemax_results import verify  # noqa: E402
from zemax_batch import build_batch_package  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(package: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        archive.extractall(target)


def test_zemax_package_is_deterministic_and_self_describing(tmp_path: Path) -> None:
    service = ExperimentService()
    rows = service.sweep({"eye_id": "chick_30_45d", "focal_length_mm": 7.5, "pupil_diameter_mm": 2.0})
    first = build_batch_package(rows)
    second = build_batch_package(rows)
    assert first.batch_id == second.batch_id
    assert first.sha256 == second.sha256
    assert first.content == second.content
    assert first.case_count == 7

    extract(first.content, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["batch_id"] == first.batch_id
    assert manifest["execution_state"] == "NOT_RUN_IN_ZEMAX"
    assert manifest["case_count"] == 7
    assert manifest["model_contract"]["ray_trace"] == "direct unpolarized paraxial rays with explicit eye-stop height"
    for relative, digest in manifest["file_sha256"].items():
        assert sha256(tmp_path / relative) == digest


def test_browser_cases_are_recalculated_and_duplicates_are_rejected() -> None:
    service = ExperimentService()
    inputs = {
        "mode": "range",
        "eye_id": "chick_30_45d",
        "focal_length_mm": 7.83,
        "axial_length_mm": 12.2,
        "pupil_diameter_mm": 2.7,
        "source_demand_D": 85,
        "external_lens_power_D": 0,
        "conservative_source_diameter_mm": 999999,
    }
    rows = service.zemax_batch_rows({"cases": [inputs]})
    assert rows[0]["conservative_source_diameter_mm"] == pytest.approx(5.9866957071)
    with pytest.raises(ValueError, match="duplicate Zemax case"):
        build_batch_package(rows + rows)
    with pytest.raises(RequestError, match="case 1"):
        service.zemax_batch_rows({"cases": [{**inputs, "focal_length_mm": 99}]})


def test_independent_verifier_passes_a_complete_synthetic_run(tmp_path: Path) -> None:
    service = ExperimentService()
    rows = [service.calculate({
        "eye_id": "adult_18y",
        "focal_length_mm": 16.7,
        "pupil_diameter_mm": 5,
        "source_demand_D": 60,
    })]
    package = build_batch_package(rows)
    batch_dir = tmp_path / "batch"
    results_dir = tmp_path / "results"
    systems_dir = results_dir / "systems"
    batch_dir.mkdir()
    systems_dir.mkdir(parents=True)
    extract(package.content, batch_dir)
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    with (batch_dir / "expected_results.csv").open(encoding="utf-8", newline="") as stream:
        expected = next(csv.DictReader(stream))
    zos_relative = f"systems/{expected['case_id']}.zos"
    zos_path = results_dir / zos_relative
    zos_path.write_bytes(b"synthetic-zos-for-verifier-unit-test")
    columns = [
        "batch_id", "case_id", "input_sha256", "opticstudio_version", "api_license_valid",
        "expected_min_y_mm", "observed_min_y_mm", "expected_max_y_mm", "observed_max_y_mm",
        "boundary_error_um", "valid_rays", "ray_error_count", "ray_vignette_count", "zos_file",
        "zos_sha256", "status", "error_type", "error_message",
    ]
    values = {
        "batch_id": manifest["batch_id"], "case_id": expected["case_id"],
        "input_sha256": expected["input_sha256"], "opticstudio_version": "24.1.0",
        "api_license_valid": "true", "expected_min_y_mm": expected["expected_min_y_mm"],
        "observed_min_y_mm": expected["expected_min_y_mm"], "expected_max_y_mm": expected["expected_max_y_mm"],
        "observed_max_y_mm": expected["expected_max_y_mm"], "boundary_error_um": "0",
        "valid_rays": "4", "ray_error_count": "0", "ray_vignette_count": "0",
        "zos_file": zos_relative, "zos_sha256": sha256(zos_path), "status": "OK",
        "error_type": "", "error_message": "",
    }
    with (results_dir / "zos_results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow(values)
    (results_dir / "run_metadata.json").write_text(json.dumps({
        "schema_version": "1.0", "batch_id": manifest["batch_id"],
        "cases_sha256": manifest["file_sha256"]["cases.csv"], "opticstudio_version": "24.1.0",
        "api_license_valid": True, "total_cases": 1, "completed_cases": 1, "failed_cases": 0,
    }), encoding="utf-8")

    report = verify(batch_dir, results_dir)
    assert report["verification_status"] == "PASS"
    assert report["passed_case_count"] == 1
    assert report["maximum_boundary_error_um"] == 0

    (batch_dir / "cases.csv").write_text("tampered", encoding="utf-8")
    tampered = verify(batch_dir, results_dir)
    assert tampered["verification_status"] == "FAIL"
    assert any("package integrity failure" in issue for issue in tampered["issues"])
