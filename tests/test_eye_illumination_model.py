import json
from pathlib import Path

import pytest


EXPERIMENT = Path(__file__).parents[1] / "experiments" / "eye_illumination"
import sys
sys.path.insert(0, str(EXPERIMENT))

from eye_model import axial_blur, defocus_bounds_for_infinity, fixed_focal_source_solution, load_eyes


@pytest.fixture(scope="module")
def eyes():
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    return load_eyes(config)


def test_fixed_focal_solution_closes_conservative_plateau_condition(eyes):
    for eye in eyes:
        for focal in eye.fixed_effective_focal_lengths_mm:
            for pupil in eye.pupil_diameters_mm:
                result = fixed_focal_source_solution(eye, 1.0 / 60.0, focal, pupil)
                assert abs(result["conservative_plateau_margin_um"]) < 1e-8
                assert result["conservative_source_diameter_mm"] > 0


def test_fixed_focal_lengths_match_ppt_endpoints_and_midpoints(eyes):
    expected = {
        "chick_30_45d": (7.5, 8.0, 8.5),
        "child_6y": (13.5, 15.1, 16.7),
        "adult_18y": (12.8, 14.75, 16.7),
    }
    for eye in eyes:
        assert eye.fixed_effective_focal_lengths_mm == expected[eye.eye_id]


def test_requested_source_demand_grid_is_60_to_120_by_10():
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    assert config["source_demands_D"] == list(range(60, 121, 10))


def test_requested_grid_uses_fixed_focal_lengths_without_fitting(eyes):
    for eye in eyes:
        solutions = []
        for demand in range(60, 121, 10):
            for focal in eye.fixed_effective_focal_lengths_mm:
                result = fixed_focal_source_solution(eye, 1.0 / demand, focal, eye.pupil_diameters_mm[-1])
                assert result["fixed_focal_length_mm"] == focal
                assert result["fixed_eye_power_D"] == pytest.approx(1000.0 / focal)
                solutions.append(result["conservative_source_diameter_mm"])
        assert len(set(round(value, 8) for value in solutions)) > 3


def test_geometric_minimum_covers_target_support(eyes):
    for eye in eyes:
        result = fixed_focal_source_solution(
            eye,
            1.0 / 60.0,
            eye.fixed_effective_focal_lengths_mm[1],
            eye.pupil_diameters_mm[-1],
        )
        assert result["geometric_coverage_margin_um"] >= -1e-8


def test_defocus_blur_is_zero_at_zero_defocus(eyes):
    for eye in eyes:
        assert defocus_bounds_for_infinity(eye, 0.0, eye.pupil_diameters_mm[-1])["blur_diameter_mm"] == 0.0


def test_nominal_axial_length_has_zero_blur(eyes):
    for eye in eyes:
        assert axial_blur(eye, eye.reported_axial_length_mm, eye.pupil_diameters_mm[-1])["blur_diameter_mm"] == pytest.approx(0.0)
