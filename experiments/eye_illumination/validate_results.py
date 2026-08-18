"""Independent numerical QA of fixed-focal results and ZOS-API checks."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def main() -> int:
    fixed = pd.read_csv(RESULTS / "fixed_focal_source_sweep.csv")
    headline = pd.read_csv(RESULTS / "headline_results.csv")
    zos = pd.read_csv(RESULTS / "zemax" / "zosapi_validation.csv")

    expected_focals = {
        "chick_30_45d": [7.5, 8.0, 8.5],
        "child_6y": [13.5, 15.1, 16.7],
        "adult_18y": [12.8, 14.75, 16.7],
    }
    observed_focals = {
        eye_id: sorted(float(value) for value in fixed.loc[fixed.eye_id == eye_id, "fixed_focal_length_mm"].unique())
        for eye_id in expected_focals
    }
    demand_levels = sorted(float(value) for value in fixed.source_demand_D.unique())
    expected_rows = 3 * 3 * 4 * 7
    zos_files = list((RESULTS / "zemax").glob("*_fixed_*.zos"))
    case_key = ["eye_id", "fixed_focal_length_mm", "pupil_diameter_mm", "source_demand_D"]
    checks = {
        "fixed_focal_sweep_rows": int(len(fixed)),
        "expected_fixed_focal_sweep_rows": expected_rows,
        "headline_rows": int(len(headline)),
        "source_demand_levels_D": demand_levels,
        "source_demand_step_D": float(np.diff(demand_levels).min()),
        "fixed_focal_lengths_mm": observed_focals,
        "expected_fixed_focal_lengths_mm": expected_focals,
        "contains_accommodation_output": bool(any("accommodation" in column for column in fixed.columns)),
        "all_conservative_sizes_at_least_geometric": bool(
            (fixed.conservative_source_diameter_mm + 1e-12 >= fixed.geometric_min_source_diameter_mm).all()
        ),
        "max_conservative_plateau_residual_um": float(fixed.conservative_plateau_margin_um.abs().max()),
        "min_geometric_coverage_margin_um": float(fixed.geometric_coverage_margin_um.min()),
        "zos_case_count": int(len(zos)),
        "zos_system_file_count": int(len(zos_files)),
        "zos_bound_max_error_um": float(zos.bound_error_um.max()),
        "opticstudio_version": str(zos.opticstudio_version.iloc[0]),
        "api_license_valid": bool(zos.api_license_valid.iloc[0]),
        "duplicate_case_count": int(fixed.duplicated(case_key).sum()),
        "missing_value_count": int(fixed.isna().sum().sum()),
        "minimum_maximum_source_pupil_ray_angle_deg": float(fixed.maximum_source_pupil_ray_angle_deg.min()),
        "maximum_maximum_source_pupil_ray_angle_deg": float(fixed.maximum_source_pupil_ray_angle_deg.max()),
        "cases_above_paraxial_angle_screen": int(
            (fixed.maximum_source_pupil_ray_angle_deg > fixed.paraxial_screening_angle_limit_deg).sum()
        ),
        "cases_below_f_number_4": int((fixed.working_f_number < 4.0).sum()),
        "validation_scope": "first-order paraxial calculation and equivalent OpticStudio Paraxial boundary only",
        "real_experiment_readiness": "NOT_READY_CALIBRATION_AND_SAFETY_REQUIRED",
    }
    checks["overall_status"] = "passed" if (
        checks["fixed_focal_sweep_rows"] == expected_rows
        and checks["headline_rows"] == 63
        and checks["source_demand_levels_D"] == [60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0]
        and checks["source_demand_step_D"] == 10.0
        and checks["fixed_focal_lengths_mm"] == expected_focals
        and not checks["contains_accommodation_output"]
        and checks["all_conservative_sizes_at_least_geometric"]
        and checks["max_conservative_plateau_residual_um"] < 1e-8
        and checks["min_geometric_coverage_margin_um"] >= -1e-8
        and checks["zos_case_count"] == 6
        and checks["zos_system_file_count"] == 6
        and checks["zos_bound_max_error_um"] < 1e-6
        and checks["api_license_valid"]
        and checks["duplicate_case_count"] == 0
        and checks["missing_value_count"] == 0
    ) else "failed"
    (RESULTS / "validation_report.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8.4, 4.9))
    x = np.arange(len(zos))
    ax.scatter(x - 0.08, zos.expected_max_y_mm, s=65, marker="o", color="#2457A6", label="Analytical upper bound")
    ax.scatter(x + 0.08, zos.observed_max_y_mm, s=50, marker="x", color="#D9782D", label="OpticStudio upper bound")
    ax.set_xticks(x, zos.case_id, rotation=28, ha="right")
    ax.set_ylabel("Retinal ray-height bound (mm)")
    ax.set_title("Fixed-focal analytical footprint and OpticStudio agree")
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES / "zosapi_cross_validation.png", dpi=180)
    plt.close(fig)

    print(json.dumps(checks, indent=2))
    return 0 if checks["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
