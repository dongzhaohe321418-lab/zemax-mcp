"""Build deterministic, self-verifying OpticStudio batch packages."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Iterable
import zipfile


APP_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = APP_DIR.parent
ZEMAX_DIR = EXPERIMENT_DIR / "zemax"
BATCH_SCHEMA_VERSION = "1.0"
RUNNER_VERSION = "1.0"
MAX_BATCH_CASES = 1000

CASE_COLUMNS = (
    "case_id",
    "eye_id",
    "mode",
    "wavelength_nm",
    "source_demand_D",
    "source_distance_mm",
    "effective_focal_length_mm",
    "axial_length_mm",
    "image_index",
    "reduced_retina_distance_mm",
    "target_diameter_mm",
    "pupil_diameter_mm",
    "external_lens_power_D",
    "external_lens_vertex_distance_mm",
    "conservative_source_diameter_mm",
    "source_mapping_coefficient",
    "pupil_mapping_coefficient",
    "input_sha256",
)

EXPECTED_COLUMNS = (
    "case_id",
    "input_sha256",
    "expected_min_y_mm",
    "expected_max_y_mm",
    "expected_valid_rays",
    "boundary_tolerance_um",
)

PACKAGE_SOURCES = {
    "scripts/ZosApiEyeBatch.cs": ZEMAX_DIR / "ZosApiEyeBatch.cs",
    "scripts/run_zemax_batch.ps1": ZEMAX_DIR / "run_zemax_batch.ps1",
    "scripts/verify_zemax_results.py": ZEMAX_DIR / "verify_zemax_results.py",
    "README_ZEMAX_BATCH.md": ZEMAX_DIR / "README_ZEMAX_BATCH.md",
    "model_snapshot/eye_model.py": EXPERIMENT_DIR / "eye_model.py",
    "model_snapshot/experiment.json": EXPERIMENT_DIR / "config" / "experiment.json",
    "model_snapshot/range_parameters.json": APP_DIR / "range_parameters.json",
}


@dataclass(frozen=True)
class BatchPackage:
    batch_id: str
    filename: str
    content: bytes
    sha256: str
    case_count: int


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _number_text(value: Any) -> str:
    return format(float(value), ".17g")


def _safe_fragment(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "case"


def _input_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": str(row["mode"]),
        "eye_id": str(row["eye_id"]),
        "wavelength_nm": float(row["wavelength_nm"]),
        "source_demand_D": float(row["source_demand_D"]),
        "source_distance_mm": float(row["source_distance_mm"]),
        "effective_focal_length_mm": float(row["effective_focal_length_mm"]),
        "axial_length_mm": float(row["axial_length_mm"]),
        "image_index": float(row["axial_length_mm"]) / float(row["reduced_retina_distance_mm"]),
        "reduced_retina_distance_mm": float(row["reduced_retina_distance_mm"]),
        "target_diameter_mm": float(row["posterior_pole_diameter_mm"]),
        "pupil_diameter_mm": float(row["pupil_diameter_mm"]),
        "external_lens_power_D": float(row["external_lens_power_D"]),
        "external_lens_vertex_distance_mm": float(row["external_lens_vertex_distance_mm"]),
        "conservative_source_diameter_mm": float(row["conservative_source_diameter_mm"]),
        "source_mapping_coefficient": float(row["source_mapping_coefficient"]),
        "pupil_mapping_coefficient": float(row["pupil_mapping_coefficient"]),
    }


def _case_id(payload: dict[str, Any], digest: str) -> str:
    return "_".join(
        (
            _safe_fragment(str(payload["eye_id"])),
            _safe_fragment(str(payload["mode"])),
            f"f{payload['effective_focal_length_mm']:g}",
            f"a{payload['axial_length_mm']:g}",
            f"p{payload['pupil_diameter_mm']:g}",
            f"d{payload['source_demand_D']:g}",
            f"x{payload['external_lens_power_D']:g}",
            digest[:10],
        )
    ).replace("-", "m").replace(".", "p")


def _expected_bounds(payload: dict[str, Any]) -> tuple[float, float]:
    source_radius = payload["conservative_source_diameter_mm"] / 2.0
    pupil_radius = payload["pupil_diameter_mm"] / 2.0
    values = [
        payload["source_mapping_coefficient"] * field * source_radius
        + payload["pupil_mapping_coefficient"] * pupil * pupil_radius
        for field in (-1.0, 1.0)
        for pupil in (-0.99, 0.99)
    ]
    return min(values), max(values)


def _csv_bytes(columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return stream.getvalue()


def build_batch_package(rows: list[dict[str, Any]]) -> BatchPackage:
    """Return a deterministic ZIP whose identity depends only on validated inputs."""
    if not rows:
        raise ValueError("Zemax batch requires at least one case")
    if len(rows) > MAX_BATCH_CASES:
        raise ValueError(f"Zemax batch is limited to {MAX_BATCH_CASES} cases")

    case_rows: list[dict[str, str]] = []
    expected_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in rows:
        payload = _input_payload(row)
        input_digest = _sha256(_canonical_json(payload))
        case_id = _case_id(payload, input_digest)
        if case_id in seen_ids:
            raise ValueError(f"duplicate Zemax case: {case_id}")
        seen_ids.add(case_id)
        minimum, maximum = _expected_bounds(payload)
        case_rows.append(
            {
                "case_id": case_id,
                "eye_id": str(payload["eye_id"]),
                "mode": str(payload["mode"]),
                **{name: _number_text(payload[name]) for name in CASE_COLUMNS[3:-1]},
                "input_sha256": input_digest,
            }
        )
        expected_rows.append(
            {
                "case_id": case_id,
                "input_sha256": input_digest,
                "expected_min_y_mm": _number_text(minimum),
                "expected_max_y_mm": _number_text(maximum),
                "expected_valid_rays": "4",
                "boundary_tolerance_um": "0.00001",
            }
        )

    cases_content = _csv_bytes(CASE_COLUMNS, case_rows)
    expected_content = _csv_bytes(EXPECTED_COLUMNS, expected_rows)
    files: dict[str, bytes] = {
        "cases.csv": cases_content,
        "expected_results.csv": expected_content,
    }
    for archive_name, source in PACKAGE_SOURCES.items():
        if not source.is_file():
            raise FileNotFoundError(f"required Zemax batch resource is missing: {source}")
        files[archive_name] = source.read_bytes()

    file_hashes = {name: _sha256(content) for name, content in sorted(files.items())}
    batch_identity = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "case_count": len(case_rows),
        "file_sha256": file_hashes,
    }
    batch_id = f"eye-zemax-{_sha256(_canonical_json(batch_identity))[:16]}"

    manifest = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "batch_id": batch_id,
        "case_count": len(case_rows),
        "execution_state": "NOT_RUN_IN_ZEMAX",
        "model_contract": {
            "system_mode": "sequential",
            "surface_model": "paraxial equivalent eye with optional paraxial external lens",
            "ray_trace": "direct unpolarized paraxial rays with explicit eye-stop height",
            "wavelength_unit": "nm",
            "length_unit": "mm",
            "ray_coordinates": {"source_height_fraction": [-1.0, 1.0], "eye_stop_height_fraction": [-0.99, 0.99]},
            "acceptance": "four valid, unvignetted rays and boundary error within declared tolerance",
        },
        "required_outputs": ["zos_results.csv", "run_metadata.json", "systems/*.zos", "verification_report.json"],
        "file_sha256": file_hashes,
    }
    files["manifest.json"] = _canonical_json(manifest) + b"\n"
    package_content = _zip_bytes(files)
    return BatchPackage(
        batch_id=batch_id,
        filename=f"{batch_id}.zip",
        content=package_content,
        sha256=_sha256(package_content),
        case_count=len(case_rows),
    )
