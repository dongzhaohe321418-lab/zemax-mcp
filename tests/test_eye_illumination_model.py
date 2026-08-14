import json
from pathlib import Path

import pytest


EXPERIMENT = Path(__file__).parents[1] / "experiments" / "eye_illumination"
import sys
sys.path.insert(0, str(EXPERIMENT))

from eye_model import axial_blur, defocus_bounds_for_infinity, focus_solution, infinity_solution, load_eyes


@pytest.fixture(scope="module")
def eyes():
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    return load_eyes(config)


def test_focused_solution_closes_imaging_condition(eyes):
    for eye in eyes:
        result = focus_solution(eye, 0.1, 0.0)
        assert abs(result["imaging_B_residual_m"]) < 1e-12
        assert result["source_diameter_mm"] > eye.posterior_pole_diameter_mm


def test_no_external_lens_accommodation_matches_source_demand(eyes):
    for eye in eyes:
        assert focus_solution(eye, 0.2, 0.0)["accommodation_D"] == pytest.approx(5.0)


def test_requested_source_demand_grid_is_60_to_120_by_10():
    config = json.loads((EXPERIMENT / "config" / "experiment.json").read_text(encoding="utf-8"))
    assert config["source_demands_D"] == list(range(60, 121, 10))


def test_requested_grid_exceeds_all_supplied_accommodation_limits(eyes):
    for eye in eyes:
        for demand in range(60, 121, 10):
            result = focus_solution(eye, 1.0 / demand, 0.0)
            assert result["accommodation_D"] == pytest.approx(demand)
            assert not result["feasible_accommodation"]


def test_negative_lens_increases_accommodation_demand(eyes):
    for eye in eyes:
        baseline = focus_solution(eye, 0.2, 0.0)["accommodation_D"]
        corrected = focus_solution(eye, 0.2, -5.0)["accommodation_D"]
        assert corrected > baseline


def test_infinity_angular_diameter_is_about_twenty_degrees(eyes):
    for eye in eyes:
        angle = infinity_solution(eye, 0.0)["angular_diameter_deg"]
        assert 19.0 < angle < 22.0


def test_defocus_blur_is_zero_at_zero_defocus(eyes):
    for eye in eyes:
        assert defocus_bounds_for_infinity(eye, 0.0, eye.pupil_diameters_mm[-1])["blur_diameter_mm"] == 0.0


def test_nominal_axial_length_has_zero_blur(eyes):
    for eye in eyes:
        assert axial_blur(eye, eye.reported_axial_length_mm, eye.pupil_diameters_mm[-1])["blur_diameter_mm"] == pytest.approx(0.0)
