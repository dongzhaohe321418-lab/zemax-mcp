"""Run the complete reduced-eye sweep and generate versionable outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from eye_model import (
    axial_blur,
    defocus_bounds_for_infinity,
    detector_metrics,
    focus_solution,
    general_mapping,
    infinity_solution,
    load_eyes,
    sample_retina,
)


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "experiment.json"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

BLUE = "#2457A6"
ORANGE = "#D9782D"
GOLD = "#B28A20"
PINK = "#B44D73"
INK = "#252A34"
GREY = "#89909A"


def save_csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(RESULTS / name, index=False, float_format="%.8g")


def style_axes(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.tick_params(colors=INK)


def run() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    eyes = load_eyes(config)
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    focused_rows: list[dict] = []
    external_reference_rows: list[dict] = []
    infinity_rows: list[dict] = []
    for eye in eyes:
        for external_power in config["external_lens_powers_D"]:
            infinity_rows.append({"eye_id": eye.eye_id, "eye_label": eye.label, "source_demand_D": 0.0, "source_distance_mm": np.inf, "external_lens_D": external_power, **infinity_solution(eye, external_power)})
        for demand in config["source_demands_D"]:
            distance_m = 1.0 / demand
            focused_rows.append({
                "eye_id": eye.eye_id,
                "eye_label": eye.label,
                "source_demand_D": demand,
                "source_distance_mm": distance_m * 1000.0,
                "external_lens_D": 0.0,
                "vertex_distance_mm": 0.0,
                "sweep_role": "requested_60_120D_no_external_lens",
                "pupil_independence_note": "Paraxial in-focus image size is independent of pupil diameter",
                **focus_solution(eye, distance_m, 0.0),
            })

        reference_demand = float(config["external_lens_reference_demand_D"])
        reference_distance_m = 1.0 / reference_demand
        for external_power in config["external_lens_powers_D"]:
            external_reference_rows.append({
                "eye_id": eye.eye_id,
                "eye_label": eye.label,
                "source_demand_D": reference_demand,
                "source_distance_mm": reference_distance_m * 1000.0,
                "external_lens_D": external_power,
                "vertex_distance_mm": eye.external_lens_vertex_distance_mm,
                "sweep_role": "external_lens_reference_10D",
                "pupil_independence_note": "Paraxial in-focus image size is independent of pupil diameter",
                **focus_solution(eye, reference_distance_m, external_power),
            })
    focused = pd.DataFrame(focused_rows)
    external_reference = pd.DataFrame(external_reference_rows)
    infinity = pd.DataFrame(infinity_rows)
    save_csv(focused, "focused_source_sweep.csv")
    save_csv(external_reference, "external_lens_reference.csv")
    save_csv(infinity, "infinity_angular_sweep.csv")

    defocus_rows: list[dict] = []
    axial_rows: list[dict] = []
    for eye in eyes:
        for pupil in eye.pupil_diameters_mm:
            for defocus in config["defocus_sweep_D"]:
                defocus_rows.append({"eye_id": eye.eye_id, "eye_label": eye.label, "pupil_diameter_mm": pupil, "defocus_D": defocus, **defocus_bounds_for_infinity(eye, defocus, pupil)})
            for axial in eye.axial_sensitivity_mm:
                axial_rows.append({"eye_id": eye.eye_id, "eye_label": eye.label, "pupil_diameter_mm": pupil, "axial_length_mm": axial, **axial_blur(eye, axial, pupil)})
    defocus = pd.DataFrame(defocus_rows)
    axial = pd.DataFrame(axial_rows)
    save_csv(defocus, "defocus_pupil_sweep.csv")
    save_csv(axial, "axial_length_sensitivity.csv")

    # Deterministic Monte Carlo checks for a focused case and a deliberately defocused case.
    adult = next(eye for eye in eyes if eye.eye_id == "adult_18y")
    focused_case = focus_solution(adult, 0.1, 0.0)
    m_source, m_pupil = general_mapping(adult, 0.1, focused_case["eye_power_D"], 0.0)
    xf, yf = sample_retina(focused_case["source_diameter_mm"] / 2000.0, 5.0 / 2000.0, m_source, m_pupil, 600_000, config["random_seed"])
    focused_metrics = detector_metrics(xf, yf, adult.target_radius_m)

    defocus_D = 10.0
    pupil_mm = 5.0
    bounds = defocus_bounds_for_infinity(adult, defocus_D, pupil_mm)
    theta_radius = np.radians(bounds["uniform_conservative_angular_diameter_deg"] / 2.0)
    # At infinity, source_radius is angular radius and m_source is reduced retina distance.
    xd, yd = sample_retina(theta_radius, pupil_mm / 2000.0, adult.reduced_retina_distance_m, -adult.reduced_retina_distance_m * defocus_D, 600_000, config["random_seed"] + 1)
    defocused_metrics = detector_metrics(xd, yd, adult.target_radius_m)
    monte_carlo_summary = {
        "sample_count_per_case": 600000,
        "seed": config["random_seed"],
        "focused_adult_10D": {key: value for key, value in focused_metrics.items() if not isinstance(value, np.ndarray)},
        "adult_infinity_plus10D_defocus": {key: value for key, value in defocused_metrics.items() if not isinstance(value, np.ndarray)},
    }
    (RESULTS / "monte_carlo_summary.json").write_text(json.dumps(monte_carlo_summary, indent=2), encoding="utf-8")

    # Chart 1: source diameter vs near demand, no external lens.
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    colors = [BLUE, ORANGE, PINK]
    for eye, color in zip(eyes, colors):
        subset = focused[(focused.eye_id == eye.eye_id) & (focused.external_lens_D == 0)]
        ax.plot(subset.source_demand_D, subset.source_diameter_mm, marker="o", linewidth=2.2, label=eye.label, color=color)
    ax.set(title="Required circular source diameter", xlabel="Accommodation demand / object vergence magnitude (D)", ylabel="Source diameter (mm)")
    ax.legend(frameon=False)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "source_diameter_vs_demand.png", dpi=180)
    plt.close(fig)

    # Chart 2: adult accommodation demand with external negative lenses.
    adult_focus = external_reference[external_reference.eye_id == "adult_18y"].sort_values("external_lens_D")
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    ax.plot(adult_focus.external_lens_D, adult_focus.accommodation_D, marker="o", linewidth=2.2, color=BLUE)
    ax.axhline(adult.accommodation_limit_D, color=ORANGE, linestyle="--", linewidth=1.4, label="Adult accommodation limit")
    ax.set(xlabel="External lens power (D)", ylabel="Required accommodation (D)", title="Adult external-lens reference at 10 D source demand")
    ax.legend(frameon=False)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "adult_accommodation_heatmap.png", dpi=180)
    plt.close(fig)

    # Chart 3: defocus blur by pupil size.
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), sharey=False)
    for ax, eye in zip(axes, eyes):
        for pupil, color in zip(eye.pupil_diameters_mm, [BLUE, GOLD, ORANGE, PINK]):
            subset = defocus[(defocus.eye_id == eye.eye_id) & (defocus.pupil_diameter_mm == pupil)]
            ax.plot(subset.defocus_D, subset.blur_diameter_mm, marker="o", label=f"{pupil:g} mm", color=color)
        ax.axhline(eye.posterior_pole_diameter_mm, color=INK, linestyle="--", linewidth=1.2, label="posterior pole")
        ax.set(title=eye.label, xlabel="Defocus (D)", ylabel="Paraxial blur diameter (mm)")
        style_axes(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Defocus blur grows linearly with pupil diameter")
    fig.tight_layout()
    fig.savefig(FIGURES / "defocus_blur_by_pupil.png", dpi=180)
    plt.close(fig)

    # Chart 4: Monte Carlo detector maps.
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.7))
    for ax, metrics, title in [
        (axes[0], focused_metrics, "Focused: adult, 10 D source"),
        (axes[1], defocused_metrics, "Defocused: adult, +10 D"),
    ]:
        hist = metrics["histogram"].T
        vmax = np.percentile(hist[hist > 0], 99) if np.any(hist > 0) else 1
        im = ax.imshow(hist, origin="lower", extent=[-3, 3, -3, 3], cmap="magma", vmin=0, vmax=vmax)
        circle = plt.Circle((0, 0), 3, fill=False, color="white", linewidth=1.0)
        ax.add_patch(circle)
        ax.set(title=title, xlabel="Retina x (mm)", ylabel="Retina y (mm)", aspect="equal")
        fig.colorbar(im, ax=ax, fraction=0.046, label="Relative ray count")
    fig.tight_layout()
    fig.savefig(FIGURES / "retinal_irradiance_monte_carlo.png", dpi=180)
    plt.close(fig)

    # Exact headline table and reproducibility manifest.
    headline = focused[[
        "eye_id", "eye_label", "source_demand_D", "source_distance_mm", "source_diameter_mm", "source_area_mm2", "accommodation_D", "feasible_accommodation"
    ]]
    save_csv(headline, "headline_results.csv")
    manifest = {
        "experiment_id": config["experiment_id"],
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
        "outputs": sorted(path.name for path in RESULTS.iterdir()) + sorted(path.name for path in FIGURES.iterdir()),
        "model_status": "executed reduced-order paraxial model; selected cases cross-validated by the ZOS-API workflow",
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
