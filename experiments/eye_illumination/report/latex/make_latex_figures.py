"""Render Chinese, Songti-labelled figures for the LaTeX report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RESULTS = EXPERIMENT / "results"
FIGURES = HERE / "figures"
sys.path.insert(0, str(EXPERIMENT))
from eye_model import detector_metrics, defocus_bounds_for_infinity, focus_solution, general_mapping, load_eyes, sample_retina


SONGTI_PATH = Path(r"C:\Windows\Fonts\simsun.ttc")
SONGTI = FontProperties(fname=str(SONGTI_PATH))
BLUE, ORANGE, GOLD, PINK, INK = "#2457A6", "#D9782D", "#B28A20", "#B44D73", "#252A34"


def style(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.tick_params(colors=INK)


def cn(ax: plt.Axes, *, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontproperties=SONGTI, fontsize=13)
    ax.set_xlabel(xlabel, fontproperties=SONGTI)
    ax.set_ylabel(ylabel, fontproperties=SONGTI)


def main() -> None:
    if not SONGTI_PATH.exists():
        raise FileNotFoundError(f"宋体文件不存在：{SONGTI_PATH}")
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10})
    focused = pd.read_csv(RESULTS / "focused_source_sweep.csv")
    defocus = pd.read_csv(RESULTS / "defocus_pupil_sweep.csv")
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    eyes = load_eyes(config)
    labels = {"chick_30_45d": "30--45日龄小鸡", "child_6y": "6岁儿童", "adult_18y": "18岁成人"}

    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    for eye, color in zip(eyes, [BLUE, ORANGE, PINK]):
        subset = focused[(focused.eye_id == eye.eye_id) & (focused.external_lens_D == 0)]
        ax.plot(subset.source_demand_D, subset.source_diameter_mm, marker="o", linewidth=2.2, label=labels[eye.eye_id], color=color)
    cn(ax, title="覆盖目标后极部所需的圆形光源直径", xlabel="物方屈光需求 / 调节需求（D）", ylabel="光源直径（mm）")
    ax.legend(frameon=False, prop=SONGTI)
    style(ax); fig.tight_layout(); fig.savefig(FIGURES / "source_diameter_cn.png", dpi=220); plt.close(fig)

    adult = focused[focused.eye_id == "adult_18y"].pivot(index="external_lens_D", columns="source_demand_D", values="accommodation_D")
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    image = ax.imshow(adult.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(adult.columns)), [f"{v:g}" for v in adult.columns])
    ax.set_yticks(range(len(adult.index)), [f"{v:g}" for v in adult.index])
    cn(ax, title="成人眼在不同物距与外置负镜片下的调节需求", xlabel="物方屈光需求（D）", ylabel="外置镜片度数（D）")
    for i in range(adult.shape[0]):
        for j in range(adult.shape[1]):
            value = adult.iloc[i, j]
            ax.text(j, i, f"{value:.1f}", ha="center", va="center", color="white" if value > 15 else INK)
    bar = fig.colorbar(image, ax=ax); bar.set_label("所需调节（D）", fontproperties=SONGTI)
    fig.tight_layout(); fig.savefig(FIGURES / "adult_accommodation_cn.png", dpi=220); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    for ax, eye in zip(axes, eyes):
        for pupil, color in zip(eye.pupil_diameters_mm, [BLUE, GOLD, ORANGE, PINK]):
            subset = defocus[(defocus.eye_id == eye.eye_id) & (defocus.pupil_diameter_mm == pupil)]
            ax.plot(subset.defocus_D, subset.blur_diameter_mm, marker="o", label=f"{pupil:g} mm", color=color)
        ax.axhline(eye.posterior_pole_diameter_mm, color=INK, linestyle="--", linewidth=1.2, label="目标直径")
        cn(ax, title=labels[eye.eye_id], xlabel="离焦（D）", ylabel="几何模糊斑直径（mm）")
        style(ax)
    axes[0].legend(frameon=False, prop=SONGTI, fontsize=8)
    fig.suptitle("离焦模糊斑随瞳孔直径近似线性增加", fontproperties=SONGTI, fontsize=14)
    fig.tight_layout(); fig.savefig(FIGURES / "defocus_blur_cn.png", dpi=220); plt.close(fig)

    adult_eye = next(eye for eye in eyes if eye.eye_id == "adult_18y")
    focused_case = focus_solution(adult_eye, 0.1, 0.0)
    ms, mp = general_mapping(adult_eye, 0.1, focused_case["eye_power_D"], 0.0)
    xf, yf = sample_retina(focused_case["source_diameter_mm"] / 2000, 5 / 2000, ms, mp, 600_000, config["random_seed"])
    fm = detector_metrics(xf, yf, adult_eye.target_radius_m)
    bounds = defocus_bounds_for_infinity(adult_eye, 10.0, 5.0)
    theta = np.radians(bounds["uniform_conservative_angular_diameter_deg"] / 2)
    xd, yd = sample_retina(theta, 5 / 2000, adult_eye.reduced_retina_distance_m, -adult_eye.reduced_retina_distance_m * 10, 600_000, config["random_seed"] + 1)
    dm = detector_metrics(xd, yd, adult_eye.target_radius_m)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.7))
    for ax, metrics, title in [(axes[0], fm, "成人眼：100 mm物距，已调焦"), (axes[1], dm, "成人眼：无穷远，+10 D离焦")]:
        hist = metrics["histogram"].T
        vmax = np.percentile(hist[hist > 0], 99)
        im = ax.imshow(hist, origin="lower", extent=[-3, 3, -3, 3], cmap="magma", vmin=0, vmax=vmax)
        ax.add_patch(plt.Circle((0, 0), 3, fill=False, color="white", linewidth=1))
        cn(ax, title=title, xlabel="视网膜 x（mm）", ylabel="视网膜 y（mm）")
        ax.set_aspect("equal"); bar = fig.colorbar(im, ax=ax, fraction=0.046); bar.set_label("相对光线计数", fontproperties=SONGTI)
    fig.tight_layout(); fig.savefig(FIGURES / "monte_carlo_cn.png", dpi=220); plt.close(fig)

    zos = pd.read_csv(RESULTS / "zemax" / "zosapi_validation.csv")
    zf = zos[zos.accommodated].copy()
    x = np.arange(len(zf))
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.scatter(x, zf.target_radius_mm, s=75, color=BLUE, label="独立模型目标")
    ax.scatter(x, zf.mean_image_y_mm.abs(), s=55, marker="x", color=ORANGE, label="OpticStudio追迹")
    ax.set_xticks(x, zf.case_id, rotation=22, ha="right")
    cn(ax, title="独立模型与OpticStudio聚焦视网膜边缘交叉验证", xlabel="验证案例", ylabel="视网膜边缘高度（mm）")
    ax.legend(frameon=False, prop=SONGTI); style(ax); fig.tight_layout(); fig.savefig(FIGURES / "zos_validation_cn.png", dpi=220); plt.close(fig)
    print(FIGURES)


if __name__ == "__main__":
    main()
