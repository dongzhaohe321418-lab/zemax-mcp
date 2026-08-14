"""Independent numerical QA of generated results and ZOS-API cross-checks."""

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
    focused = pd.read_csv(RESULTS / "focused_source_sweep.csv")
    external_reference = pd.read_csv(RESULTS / "external_lens_reference.csv")
    headline = pd.read_csv(RESULTS / "headline_results.csv")
    zos = pd.read_csv(RESULTS / "zemax" / "zosapi_validation.csv")

    focused_zos = zos[zos["accommodated"]].copy()
    focused_zos["edge_error_um"] = 1000.0 * (focused_zos["mean_image_y_mm"].abs() - focused_zos["target_radius_mm"]).abs()
    focused_zos["expected_rms_um"] = 0.0

    unfocused = zos[~zos["accommodated"]].iloc[0]
    expected_width_mm = (unfocused["eye_focal_length_mm"] / 1000.0) * unfocused["accommodation_D"] * unfocused["pupil_diameter_mm"] * 0.99
    observed_width_mm = unfocused["max_image_y_mm"] - unfocused["min_image_y_mm"]

    checks = {
        "focused_zos_edge_max_error_um": float(focused_zos["edge_error_um"].max()),
        "focused_zos_rms_max_um": float(focused_zos["rms_spread_um"].max()),
        "unaccommodated_expected_spread_mm": float(expected_width_mm),
        "unaccommodated_observed_spread_mm": float(observed_width_mm),
        "unaccommodated_spread_error_um": float(1000.0 * abs(observed_width_mm - expected_width_mm)),
        "headline_rows": int(len(headline)),
        "full_focused_sweep_rows": int(len(focused)),
        "external_lens_reference_rows": int(len(external_reference)),
        "source_demand_levels_D": sorted(float(value) for value in focused["source_demand_D"].unique()),
        "source_demand_step_D": float(np.diff(sorted(focused["source_demand_D"].unique())).min()),
        "all_requested_cases_exceed_accommodation_limits": bool((~focused["feasible_accommodation"]).all()),
        "all_imaging_residuals_below_1e_12_m": bool((focused["imaging_B_residual_m"].abs() < 1e-12).all()),
        "opticstudio_version": str(zos["opticstudio_version"].iloc[0]),
        "api_license_valid": bool(zos["api_license_valid"].iloc[0]),
    }
    checks["overall_status"] = "passed" if (
        checks["focused_zos_edge_max_error_um"] < 1e-6
        and checks["focused_zos_rms_max_um"] < 1e-6
        and checks["unaccommodated_spread_error_um"] < 1e-6
        and checks["all_imaging_residuals_below_1e_12_m"]
        and checks["headline_rows"] == 21
        and checks["full_focused_sweep_rows"] == 21
        and checks["external_lens_reference_rows"] == 21
        and checks["source_demand_levels_D"] == [60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0]
        and checks["source_demand_step_D"] == 10.0
        and checks["all_requested_cases_exceed_accommodation_limits"]
    ) else "failed"
    (RESULTS / "validation_report.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    x = np.arange(len(focused_zos))
    ax.scatter(x, focused_zos["target_radius_mm"], s=70, marker="o", color="#2457A6", label="Independent target")
    ax.scatter(x, focused_zos["mean_image_y_mm"].abs(), s=48, marker="x", color="#D9782D", label="OpticStudio ray trace")
    ax.set_xticks(x, focused_zos["case_id"], rotation=25, ha="right")
    ax.set_ylabel("Retinal edge height (mm)")
    ax.set_title("Independent model and OpticStudio agree on focused retinal edge")
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
