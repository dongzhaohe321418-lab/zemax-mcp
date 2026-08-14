"""Run the fixed-focal reduced-eye sweep and generate versionable outputs."""

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
    fixed_focal_source_solution,
    general_mapping,
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
    frame.to_csv(RESULTS / name, index=False, float_format="%.10g")


def style_axes(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.tick_params(colors=INK)


def run() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    eyes = load_eyes(config)
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for eye in eyes:
        for focal_length_mm in eye.fixed_effective_focal_lengths_mm:
            for pupil_diameter_mm in eye.pupil_diameters_mm:
                for demand in config["source_demands_D"]:
                    distance_m = 1.0 / demand
                    rows.append({
                        "eye_id": eye.eye_id,
                        "eye_label": eye.label,
                        "source_demand_D": demand,
                        "source_distance_mm": 1000.0 * distance_m,
                        "posterior_pole_diameter_mm": eye.posterior_pole_diameter_mm,
                        "reported_axial_length_mm": eye.reported_axial_length_mm,
                        "image_medium_refractive_index": eye.image_medium_refractive_index,
                        "external_lens_D": 0.0,
                        "sweep_role": "fixed_focal_object_distance_source_sizing",
                        **fixed_focal_source_solution(
                            eye,
                            distance_m,
                            focal_length_mm,
                            pupil_diameter_mm,
                        ),
                    })
    fixed = pd.DataFrame(rows)
    save_csv(fixed, "fixed_focal_source_sweep.csv")

    # Headline lookup uses the largest configured pupil for each eye, keeping all
    # three fixed focal lengths and all seven requested object distances.
    headline_parts = []
    for eye in eyes:
        headline_parts.append(fixed[(fixed.eye_id == eye.eye_id) & (fixed.pupil_diameter_mm == max(eye.pupil_diameters_mm))])
    headline = pd.concat(headline_parts, ignore_index=True)
    save_csv(headline, "headline_results.csv")

    defocus_rows: list[dict] = []
    axial_rows: list[dict] = []
    for eye in eyes:
        for pupil in eye.pupil_diameters_mm:
            for defocus in config["defocus_sweep_D"]:
                defocus_rows.append({
                    "eye_id": eye.eye_id,
                    "eye_label": eye.label,
                    "reference_focal_length_mm": eye.reference_focal_length_mm,
                    "pupil_diameter_mm": pupil,
                    "defocus_D": defocus,
                    **defocus_bounds_for_infinity(eye, defocus, pupil),
                })
            for axial in eye.axial_sensitivity_mm:
                axial_rows.append({
                    "eye_id": eye.eye_id,
                    "eye_label": eye.label,
                    "reference_focal_length_mm": eye.reference_focal_length_mm,
                    "pupil_diameter_mm": pupil,
                    "axial_length_mm": axial,
                    **axial_blur(eye, axial, pupil),
                })
    defocus = pd.DataFrame(defocus_rows)
    axial = pd.DataFrame(axial_rows)
    save_csv(defocus, "defocus_pupil_sweep.csv")
    save_csv(axial, "axial_length_sensitivity.csv")

    # Deterministic Monte Carlo comparison: geometric minimum versus the
    # conservative full-overlap design at one fixed adult focal length.
    adult = next(eye for eye in eyes if eye.eye_id == "adult_18y")
    demand_D = 60.0
    focal_mm = 16.7
    pupil_mm = 5.0
    distance_m = 1.0 / demand_D
    solution = fixed_focal_source_solution(adult, distance_m, focal_mm, pupil_mm)
    ms, mp = general_mapping(adult, distance_m, 1000.0 / focal_mm)
    cases = {}
    maps = {}
    for index, (name, diameter_key) in enumerate([
        ("geometric_minimum", "geometric_min_source_diameter_mm"),
        ("conservative_full_overlap", "conservative_source_diameter_mm"),
    ]):
        x, y = sample_retina(
            solution[diameter_key] / 2000.0,
            pupil_mm / 2000.0,
            ms,
            mp,
            600_000,
            config["random_seed"] + index,
        )
        metrics = detector_metrics(x, y, adult.target_radius_m)
        cases[name] = {key: value for key, value in metrics.items() if not isinstance(value, np.ndarray)}
        maps[name] = metrics
    monte_carlo_summary = {
        "sample_count_per_case": 600000,
        "seed": config["random_seed"],
        "eye_id": adult.eye_id,
        "fixed_focal_length_mm": focal_mm,
        "pupil_diameter_mm": pupil_mm,
        "source_demand_D": demand_D,
        "source_distance_mm": 1000.0 / demand_D,
        **cases,
    }
    (RESULTS / "monte_carlo_summary.json").write_text(json.dumps(monte_carlo_summary, indent=2), encoding="utf-8")

    # Chart 1: conservative source diameter by demand, with one panel per eye.
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.6), sharey=False)
    focal_colors = [BLUE, ORANGE, PINK]
    for ax, eye in zip(axes, eyes):
        subset_eye = headline[headline.eye_id == eye.eye_id]
        for focal, color in zip(eye.fixed_effective_focal_lengths_mm, focal_colors):
            subset = subset_eye[np.isclose(subset_eye.fixed_focal_length_mm, focal)]
            ax.plot(
                subset.source_demand_D,
                subset.conservative_source_diameter_mm,
                marker="o",
                linewidth=2.0,
                color=color,
                label=f"f={focal:g} mm",
            )
        ax.set(
            title=eye.label,
            xlabel="Object-side requirement (D)",
            ylabel="Conservative source diameter (mm)",
        )
        ax.legend(frameon=False, fontsize=8)
        style_axes(ax)
    fig.suptitle("Fixed focal lengths: conservative source size at the largest pupil")
    fig.tight_layout()
    fig.savefig(FIGURES / "source_diameter_vs_demand.png", dpi=180)
    plt.close(fig)

    # Chart 2: pupil dependence for the adult model at the two endpoint demands.
    adult_fixed = fixed[(fixed.eye_id == "adult_18y") & (fixed.source_demand_D.isin([60, 120]))]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5), sharey=True)
    for ax, demand in zip(axes, [60, 120]):
        subset_demand = adult_fixed[adult_fixed.source_demand_D == demand]
        for focal, color in zip(adult.fixed_effective_focal_lengths_mm, focal_colors):
            subset = subset_demand[np.isclose(subset_demand.fixed_focal_length_mm, focal)]
            ax.plot(
                subset.pupil_diameter_mm,
                subset.conservative_source_diameter_mm,
                marker="o",
                linewidth=2.0,
                color=color,
                label=f"f={focal:g} mm",
            )
        ax.set(title=f"Adult, {demand} D", xlabel="Pupil diameter (mm)", ylabel="Conservative source diameter (mm)")
        style_axes(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Pupil and fixed focal length jointly determine source size")
    fig.tight_layout()
    fig.savefig(FIGURES / "fixed_focal_pupil_comparison.png", dpi=180)
    plt.close(fig)

    # Chart 3: defocus blur by pupil size, retained as a sensitivity view.
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

    # Chart 4: Monte Carlo detector maps for the two source-sizing definitions.
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.7))
    for ax, name, title in [
        (axes[0], "geometric_minimum", "Geometric minimum"),
        (axes[1], "conservative_full_overlap", "Conservative full-overlap"),
    ]:
        hist = maps[name]["histogram"].T
        vmax = np.percentile(hist[hist > 0], 99) if np.any(hist > 0) else 1
        im = ax.imshow(hist, origin="lower", extent=[-3, 3, -3, 3], cmap="magma", vmin=0, vmax=vmax)
        ax.add_patch(plt.Circle((0, 0), 3, fill=False, color="white", linewidth=1.0))
        ax.set(title=title, xlabel="Retina x (mm)", ylabel="Retina y (mm)", aspect="equal")
        fig.colorbar(im, ax=ax, fraction=0.046, label="Relative ray count")
    fig.tight_layout()
    fig.savefig(FIGURES / "retinal_irradiance_monte_carlo.png", dpi=180)
    plt.close(fig)

    manifest = {
        "experiment_id": config["experiment_id"],
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
        "main_sweep_rows": int(len(fixed)),
        "headline_rows": int(len(headline)),
        "outputs": sorted(path.name for path in RESULTS.iterdir()) + sorted(path.name for path in FIGURES.iterdir()),
        "model_status": "executed fixed-focal reduced-eye model; selected footprint bounds cross-validated by ZOS-API",
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
