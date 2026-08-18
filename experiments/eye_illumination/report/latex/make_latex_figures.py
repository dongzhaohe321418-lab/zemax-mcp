"""Create Chinese fixed-focal figures for the LaTeX report."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RESULTS = EXPERIMENT / "results"
FIGURES = HERE / "figures"
sys.path.insert(0, str(EXPERIMENT))

from eye_model import detector_metrics, fixed_focal_source_solution, general_mapping, load_eyes, sample_retina


BLUE, ORANGE, PINK, GOLD, INK = "#2457A6", "#D9782D", "#B44D73", "#B28A20", "#252A34"


def setup() -> None:
    font_path = Path("C:/Windows/Fonts/simsun.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def style(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, color="#E5E7EB", linewidth=0.7)


def main() -> None:
    setup()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fixed = pd.read_csv(RESULTS / "fixed_focal_source_sweep.csv")
    headline = pd.read_csv(RESULTS / "headline_results.csv")
    zos = pd.read_csv(RESULTS / "zemax" / "zosapi_validation.csv")
    defocus = pd.read_csv(RESULTS / "defocus_pupil_sweep.csv")
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    eyes = load_eyes(config)
    labels = {"chick_30_45d": "30–45日龄小鸡", "child_6y": "6岁儿童", "adult_18y": "18岁成人"}
    colors = [BLUE, ORANGE, PINK]

    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.5))
    for ax, eye in zip(axes, eyes):
        subset_eye = headline[headline.eye_id == eye.eye_id]
        for focal, color in zip(eye.fixed_effective_focal_lengths_mm, colors):
            subset = subset_eye[np.isclose(subset_eye.fixed_focal_length_mm, focal)]
            ax.plot(subset.source_demand_D, subset.conservative_source_diameter_mm, marker="o", linewidth=2, color=color, label=f"f={focal:g} mm")
        ax.set_title(labels[eye.eye_id])
        ax.set_xlabel("物方需求（D）")
        ax.set_ylabel("保守光源直径（mm）")
        ax.legend(frameon=False, fontsize=8)
        style(ax)
    fig.suptitle("三个固定焦距下的保守光源直径（各模型最大瞳孔）")
    fig.tight_layout()
    fig.savefig(FIGURES / "source_diameter_cn.png", dpi=220)
    plt.close(fig)

    adult = next(eye for eye in eyes if eye.eye_id == "adult_18y")
    adult_fixed = fixed[(fixed.eye_id == "adult_18y") & (fixed.source_demand_D.isin([60, 120]))]
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4), sharey=True)
    for ax, demand in zip(axes, [60, 120]):
        for focal, color in zip(adult.fixed_effective_focal_lengths_mm, colors):
            subset = adult_fixed[(adult_fixed.source_demand_D == demand) & np.isclose(adult_fixed.fixed_focal_length_mm, focal)]
            ax.plot(subset.pupil_diameter_mm, subset.conservative_source_diameter_mm, marker="o", linewidth=2, color=color, label=f"f={focal:g} mm")
        ax.set_title(f"成人眼，{demand} D")
        ax.set_xlabel("瞳孔直径（mm）")
        ax.set_ylabel("保守光源直径（mm）")
        style(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("固定焦距与瞳孔共同决定光源尺寸")
    fig.tight_layout()
    fig.savefig(FIGURES / "fixed_focal_pupil_cn.png", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13.3, 4.2))
    for ax, eye in zip(axes, eyes):
        for pupil, color in zip(eye.pupil_diameters_mm, [BLUE, GOLD, ORANGE, PINK]):
            subset = defocus[(defocus.eye_id == eye.eye_id) & (defocus.pupil_diameter_mm == pupil)]
            ax.plot(subset.defocus_D, subset.blur_diameter_mm, marker="o", color=color, label=f"{pupil:g} mm")
        ax.axhline(eye.posterior_pole_diameter_mm, color=INK, linestyle="--", linewidth=1.2)
        ax.set_title(labels[eye.eye_id])
        ax.set_xlabel("等效离焦（D）")
        ax.set_ylabel("模糊斑直径（mm）")
        style(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("瞳孔直径控制固定像面上的离焦 footprint")
    fig.tight_layout()
    fig.savefig(FIGURES / "defocus_blur_cn.png", dpi=220)
    plt.close(fig)

    solution = fixed_focal_source_solution(adult, 1.0 / 60.0, 16.7, 5.0)
    ms, mp = general_mapping(adult, 1.0 / 60.0, 1000.0 / 16.7)
    maps = []
    for index, key in enumerate(["geometric_min_source_diameter_mm", "conservative_source_diameter_mm"]):
        x, y = sample_retina(solution[key] / 2000.0, 5.0 / 2000.0, ms, mp, 600_000, config["random_seed"] + index)
        maps.append(detector_metrics(x, y, adult.target_radius_m))
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.7))
    for ax, metrics, title in zip(axes, maps, ["几何最小尺寸", "保守全重叠尺寸"]):
        hist = metrics["histogram"].T
        vmax = np.percentile(hist[hist > 0], 99) if np.any(hist > 0) else 1
        im = ax.imshow(hist, origin="lower", extent=[-3, 3, -3, 3], cmap="magma", vmin=0, vmax=vmax)
        ax.add_patch(plt.Circle((0, 0), 3, fill=False, color="white", linewidth=1.0))
        ax.set_title(title)
        ax.set_xlabel("视网膜 x（mm）")
        ax.set_ylabel("视网膜 y（mm）")
        ax.set_aspect("equal")
        fig.colorbar(im, ax=ax, fraction=0.046, label="相对光线计数")
    fig.tight_layout()
    fig.savefig(FIGURES / "monte_carlo_cn.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.3, 4.8))
    x = np.arange(len(zos))
    ax.scatter(x - 0.08, zos.expected_max_y_mm, s=65, color=BLUE, label="解析上界")
    ax.scatter(x + 0.08, zos.observed_max_y_mm, s=50, marker="x", color=ORANGE, label="OpticStudio 上界")
    ax.set_xticks(x, zos.case_id, rotation=28, ha="right")
    ax.set_ylabel("视网膜光线高度上界（mm）")
    ax.set_title("固定焦距解析 footprint 与 OpticStudio 一致")
    ax.legend(frameon=False)
    style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "zos_validation_cn.png", dpi=220)
    plt.close(fig)

    # Model-domain diagnostic: this is intentionally a screening figure, not a
    # claim that a single angular threshold certifies paraxial validity.
    order = ["chick_30_45d", "child_6y", "adult_18y"]
    y = np.arange(len(order))
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    angle_min = []
    angle_median = []
    angle_max = []
    below_f4 = []
    at_or_above_f4 = []
    for eye_id in order:
        subset = fixed[fixed.eye_id == eye_id]
        values = subset.maximum_source_pupil_ray_angle_deg.to_numpy()
        angle_min.append(float(np.min(values)))
        angle_median.append(float(np.median(values)))
        angle_max.append(float(np.max(values)))
        below = int((subset.working_f_number < 4.0).sum())
        below_f4.append(below)
        at_or_above_f4.append(len(subset) - below)
    angle_min = np.array(angle_min)
    angle_median = np.array(angle_median)
    angle_max = np.array(angle_max)
    axes[0].errorbar(
        angle_median,
        y,
        xerr=[angle_median - angle_min, angle_max - angle_median],
        fmt="o",
        color=BLUE,
        ecolor=BLUE,
        capsize=5,
        linewidth=2,
        label="最小—中位—最大",
    )
    axes[0].axvline(10.0, color=ORANGE, linestyle="--", linewidth=1.6, label="项目筛查线 10°")
    axes[0].set_yticks(y, [labels[item] for item in order])
    axes[0].set_xlabel("保守源边缘—瞳孔边缘最大角（°）")
    axes[0].set_title("全部 252 工况超过 10°")
    axes[0].legend(frameon=False, fontsize=8)
    style(axes[0])

    axes[1].barh(y, below_f4, color=ORANGE, edgecolor=INK, hatch="//", label="F/# < 4")
    axes[1].barh(
        y,
        at_or_above_f4,
        left=below_f4,
        color="#D8DEE8",
        edgecolor=INK,
        label="F/# ≥ 4",
    )
    axes[1].set_yticks(y, [labels[item] for item in order])
    axes[1].set_xlabel("工况数（每个模型 84）")
    axes[1].set_title("工作 F 数筛查")
    axes[1].legend(frameon=False, fontsize=8)
    style(axes[1])
    fig.suptitle("近轴模型适用性诊断（筛查不等于实验放行）")
    fig.tight_layout()
    fig.savefig(FIGURES / "model_applicability_cn.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
