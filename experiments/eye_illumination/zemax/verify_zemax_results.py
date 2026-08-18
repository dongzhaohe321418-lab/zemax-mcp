"""Independently verify one OpticStudio batch run and seal its audit report."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value:
            raise ValueError(f"{path.name} contains a blank {key}")
        if value in result:
            raise ValueError(f"{path.name} contains duplicate {key}: {value}")
        result[value] = row
    return result


def close_enough(actual: str, expected: str, tolerance: float = 1e-12) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)


def verify(batch_dir: Path, results_dir: Path) -> dict[str, Any]:
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    integrity: dict[str, bool] = {}
    for relative, expected_hash in manifest["file_sha256"].items():
        path = batch_dir / Path(relative)
        valid = path.is_file() and sha256(path) == expected_hash
        integrity[relative] = valid
        if not valid:
            issues.append(f"package integrity failure: {relative}")

    expected = read_csv(batch_dir / "expected_results.csv", "case_id")
    cases = read_csv(batch_dir / "cases.csv", "case_id")
    results_path = results_dir / "zos_results.csv"
    metadata_path = results_dir / "run_metadata.json"
    if not results_path.is_file():
        issues.append("missing zos_results.csv")
        actual: dict[str, dict[str, str]] = {}
    else:
        actual = read_csv(results_path, "case_id")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    if not metadata:
        issues.append("missing run_metadata.json")

    expected_ids = set(expected)
    if set(cases) != expected_ids:
        issues.append("case list and expected-results case IDs differ")
    missing = sorted(expected_ids - set(actual))
    extra = sorted(set(actual) - expected_ids)
    if missing:
        issues.append(f"missing result cases: {', '.join(missing[:10])}")
    if extra:
        issues.append(f"unexpected result cases: {', '.join(extra[:10])}")

    passed = 0
    failed = 0
    maximum_error_um = 0.0
    versions: set[str] = set()
    case_findings: list[dict[str, Any]] = []
    for case_id in sorted(expected_ids):
        if case_id not in actual:
            failed += 1
            continue
        target = expected[case_id]
        observed = actual[case_id]
        local: list[str] = []
        if observed.get("batch_id") != manifest["batch_id"]:
            local.append("batch_id mismatch")
        if observed.get("input_sha256") != target["input_sha256"]:
            local.append("input hash mismatch")
        if observed.get("status") != "OK":
            local.append(f"runner status is {observed.get('status', 'missing')}")
        if observed.get("api_license_valid", "").lower() != "true":
            local.append("ZOS-API license was not reported valid")
        try:
            if int(observed.get("valid_rays", "0")) != int(target["expected_valid_rays"]):
                local.append("valid-ray count mismatch")
            if int(observed.get("ray_error_count", "0")) != 0:
                local.append("ray errors reported")
            if int(observed.get("ray_vignette_count", "0")) != 0:
                local.append("vignetted rays reported")
            if not close_enough(observed["expected_min_y_mm"], target["expected_min_y_mm"]):
                local.append("C# and Python minimum-bound expectations differ")
            if not close_enough(observed["expected_max_y_mm"], target["expected_max_y_mm"]):
                local.append("C# and Python maximum-bound expectations differ")
            error_um = float(observed["boundary_error_um"])
            maximum_error_um = max(maximum_error_um, error_um)
            if error_um > float(target["boundary_tolerance_um"]):
                local.append("boundary error exceeds tolerance")
        except (KeyError, TypeError, ValueError) as exc:
            local.append(f"invalid numeric result: {type(exc).__name__}")

        zos_relative = observed.get("zos_file", "")
        zos_path = results_dir / Path(zos_relative) if zos_relative else None
        if zos_path is None or not zos_path.is_file():
            local.append("saved .zos system is missing")
        elif sha256(zos_path) != observed.get("zos_sha256"):
            local.append("saved .zos hash mismatch")
        version = observed.get("opticstudio_version", "")
        if not version:
            local.append("OpticStudio version is missing")
        else:
            versions.add(version)

        if local:
            failed += 1
            case_findings.append({"case_id": case_id, "status": "FAIL", "issues": local})
        else:
            passed += 1

    if metadata:
        if metadata.get("batch_id") != manifest["batch_id"]:
            issues.append("run_metadata batch_id mismatch")
        if metadata.get("cases_sha256") != manifest["file_sha256"]["cases.csv"]:
            issues.append("run_metadata cases hash mismatch")
        if metadata.get("api_license_valid") is not True:
            issues.append("run_metadata does not confirm a valid API license")
        if int(metadata.get("total_cases", -1)) != manifest["case_count"]:
            issues.append("run_metadata total case count mismatch")
        if int(metadata.get("failed_cases", -1)) != 0:
            issues.append("runner reported failed cases")

    result_hashes: dict[str, str] = {}
    for path in sorted(results_dir.rglob("*")):
        if path.is_file() and path.name != "verification_report.json" and "_build" not in path.parts:
            result_hashes[path.relative_to(results_dir).as_posix()] = sha256(path)

    overall = "PASS" if not issues and failed == 0 and passed == manifest["case_count"] else "FAIL"
    return {
        "schema_version": "1.0",
        "verification_status": overall,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": manifest["batch_id"],
        "batch_manifest_sha256": sha256(manifest_path),
        "package_integrity": {"status": "PASS" if all(integrity.values()) else "FAIL", "files": integrity},
        "opticstudio_versions": sorted(versions),
        "api_license_valid": bool(metadata.get("api_license_valid", False)),
        "expected_case_count": manifest["case_count"],
        "passed_case_count": passed,
        "failed_case_count": failed,
        "maximum_boundary_error_um": maximum_error_um,
        "issues": issues,
        "case_findings": case_findings,
        "result_file_sha256": result_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="replace an existing verification report")
    args = parser.parse_args()
    batch_dir = args.batch_dir.resolve()
    results_dir = args.results_dir.resolve()
    report_path = results_dir / "verification_report.json"
    if report_path.exists() and not args.force:
        print(f"Refusing to overwrite existing audit report: {report_path}", file=sys.stderr)
        return 2
    try:
        report = verify(batch_dir, results_dir)
    except Exception as exc:
        print(f"Verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERIFICATION_STATUS={report['verification_status']}")
    print(f"VERIFICATION_REPORT={report_path}")
    print(f"PASSED_CASES={report['passed_case_count']}")
    print(f"FAILED_CASES={report['failed_case_count']}")
    print(f"MAX_BOUNDARY_ERROR_UM={report['maximum_boundary_error_um']:.17g}")
    return 0 if report["verification_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

