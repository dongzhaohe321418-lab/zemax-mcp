"""Paraxial reduced-eye illumination model used for reproducible sweeps.

Ray state is [height, reduced angle] where reduced angle is n*theta. Distances
are metres internally and optical powers are diopters.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


def translation(distance_m: float, refractive_index: float = 1.0) -> np.ndarray:
    return np.array([[1.0, distance_m / refractive_index], [0.0, 1.0]])


def thin_lens(power_D: float) -> np.ndarray:
    return np.array([[1.0, 0.0], [-power_D, 1.0]])


@dataclass(frozen=True)
class Eye:
    eye_id: str
    label: str
    effective_focal_length_mm: float
    reported_axial_length_mm: float
    posterior_pole_diameter_mm: float
    accommodation_limit_D: float
    pupil_diameters_mm: tuple[float, ...]
    axial_sensitivity_mm: tuple[float, ...]
    external_lens_vertex_distance_mm: float

    @property
    def baseline_power_D(self) -> float:
        return 1000.0 / self.effective_focal_length_mm

    @property
    def reduced_retina_distance_m(self) -> float:
        return 1.0 / self.baseline_power_D

    @property
    def target_radius_m(self) -> float:
        return self.posterior_pole_diameter_mm / 2000.0


def pre_eye_matrix(source_distance_m: float, external_power_D: float, vertex_distance_m: float) -> np.ndarray:
    if not math.isfinite(source_distance_m) or source_distance_m <= 0:
        raise ValueError("source_distance_m must be finite and positive")
    if vertex_distance_m < 0 or vertex_distance_m >= source_distance_m:
        raise ValueError("vertex distance must lie between source and eye")
    return translation(vertex_distance_m) @ thin_lens(external_power_D) @ translation(source_distance_m - vertex_distance_m)


def focus_solution(eye: Eye, source_distance_m: float, external_power_D: float = 0.0) -> dict[str, float | bool]:
    # A zero-power external surface is optically absent, so its provisional
    # mechanical vertex distance must not invalidate ultra-near no-lens cases.
    vertex_m = 0.0 if external_power_D == 0.0 else eye.external_lens_vertex_distance_mm / 1000.0
    pre = pre_eye_matrix(source_distance_m, external_power_D, vertex_m)
    b = float(pre[0, 1])
    d = float(pre[1, 1])
    accommodation_D = d / b
    eye_power_D = eye.baseline_power_D + accommodation_D
    total = translation(eye.reduced_retina_distance_m) @ thin_lens(eye_power_D) @ pre
    magnification = float(total[0, 0])
    source_diameter_mm = eye.posterior_pole_diameter_mm / abs(magnification)
    return {
        "accommodation_D": accommodation_D,
        "eye_power_D": eye_power_D,
        "magnification": magnification,
        "source_diameter_mm": source_diameter_mm,
        "source_area_mm2": math.pi * (source_diameter_mm / 2.0) ** 2,
        "feasible_accommodation": 0.0 <= accommodation_D <= eye.accommodation_limit_D + 1e-9,
        "imaging_B_residual_m": float(total[0, 1]),
    }


def infinity_solution(eye: Eye, external_power_D: float = 0.0) -> dict[str, float | bool]:
    vertex_m = eye.external_lens_vertex_distance_mm / 1000.0
    field_scale = eye.reduced_retina_distance_m / (1.0 - vertex_m * external_power_D)
    accommodation_D = -external_power_D / (1.0 - vertex_m * external_power_D)
    angular_diameter_rad = (eye.posterior_pole_diameter_mm / 1000.0) / abs(field_scale)
    return {
        "accommodation_D": accommodation_D,
        "eye_power_D": eye.baseline_power_D + accommodation_D,
        "angular_diameter_rad": angular_diameter_rad,
        "angular_diameter_deg": math.degrees(angular_diameter_rad),
        "feasible_accommodation": 0.0 <= accommodation_D <= eye.accommodation_limit_D + 1e-9,
    }


def general_mapping(
    eye: Eye,
    source_distance_m: float,
    eye_power_D: float,
    external_power_D: float = 0.0,
) -> tuple[float, float]:
    """Return retina coefficients: y_retina = m_source*y_source + m_pupil*y_pupil."""
    vertex_m = 0.0 if external_power_D == 0.0 else eye.external_lens_vertex_distance_mm / 1000.0
    pre = pre_eye_matrix(source_distance_m, external_power_D, vertex_m)
    total = translation(eye.reduced_retina_distance_m) @ thin_lens(eye_power_D) @ pre
    a_pre, b_pre = float(pre[0, 0]), float(pre[0, 1])
    a_total, b_total = float(total[0, 0]), float(total[0, 1])
    return a_total - b_total * a_pre / b_pre, b_total / b_pre


def defocus_bounds_for_infinity(eye: Eye, defocus_D: float, pupil_diameter_mm: float) -> dict[str, float]:
    t = eye.reduced_retina_distance_m
    pupil_radius_m = pupil_diameter_mm / 2000.0
    blur_radius_m = abs(t * defocus_D) * pupil_radius_m
    geometric_theta_radius = max(0.0, eye.target_radius_m - blur_radius_m) / t
    uniform_theta_radius = (eye.target_radius_m + blur_radius_m) / t
    return {
        "blur_diameter_mm": 2000.0 * blur_radius_m,
        "geometric_min_angular_diameter_deg": math.degrees(2.0 * geometric_theta_radius),
        "uniform_conservative_angular_diameter_deg": math.degrees(2.0 * uniform_theta_radius),
    }


def axial_blur(eye: Eye, axial_length_mm: float, pupil_diameter_mm: float, image_index: float = 1.336) -> dict[str, float]:
    delta_physical_m = (axial_length_mm - eye.reported_axial_length_mm) / 1000.0
    reduced_delta_m = delta_physical_m / image_index
    pupil_radius_m = pupil_diameter_mm / 2000.0
    blur_radius_m = abs(reduced_delta_m * eye.baseline_power_D) * pupil_radius_m
    equivalent_defocus_D = -reduced_delta_m * eye.baseline_power_D**2
    return {
        "axial_delta_mm": axial_length_mm - eye.reported_axial_length_mm,
        "equivalent_defocus_D": equivalent_defocus_D,
        "blur_diameter_mm": 2000.0 * blur_radius_m,
    }


def sample_retina(
    source_radius: float,
    pupil_radius: float,
    m_source: float,
    m_pupil: float,
    sample_count: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    r_source = source_radius * np.sqrt(rng.random(sample_count))
    phi_source = 2 * np.pi * rng.random(sample_count)
    r_pupil = pupil_radius * np.sqrt(rng.random(sample_count))
    phi_pupil = 2 * np.pi * rng.random(sample_count)
    x = m_source * r_source * np.cos(phi_source) + m_pupil * r_pupil * np.cos(phi_pupil)
    y = m_source * r_source * np.sin(phi_source) + m_pupil * r_pupil * np.sin(phi_pupil)
    return x, y


def detector_metrics(x: np.ndarray, y: np.ndarray, target_radius_m: float, bins: int = 101) -> dict[str, float | np.ndarray]:
    limits = [[-target_radius_m, target_radius_m], [-target_radius_m, target_radius_m]]
    hist, x_edges, y_edges = np.histogram2d(x, y, bins=bins, range=limits)
    centers = (x_edges[:-1] + x_edges[1:]) / 2
    xx, yy = np.meshgrid(centers, centers, indexing="ij")
    mask = xx**2 + yy**2 <= target_radius_m**2
    values = hist[mask]
    mean = float(values.mean())
    p10 = float(np.percentile(values, 10))
    return {
        "histogram": hist,
        "roi_mask": mask,
        "captured_ray_fraction": float(np.mean(x**2 + y**2 <= target_radius_m**2)),
        "p10_to_mean_uniformity": p10 / mean if mean else 0.0,
        "pixels_at_least_half_mean": float(np.mean(values >= 0.5 * mean)) if mean else 0.0,
    }


def load_eyes(config: dict) -> list[Eye]:
    return [
        Eye(
            eye_id=item["id"],
            label=item["label"],
            effective_focal_length_mm=item["effective_focal_length_mm"],
            reported_axial_length_mm=item["reported_axial_length_mm"],
            posterior_pole_diameter_mm=item["posterior_pole_diameter_mm"],
            accommodation_limit_D=item["accommodation_limit_D"],
            pupil_diameters_mm=tuple(item["pupil_diameters_mm"]),
            axial_sensitivity_mm=tuple(item["axial_sensitivity_mm"]),
            external_lens_vertex_distance_mm=item["external_lens_vertex_distance_mm"],
        )
        for item in config["eyes"]
    ]
