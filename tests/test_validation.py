import pytest
from pydantic import ValidationError

from models import MTFRequest, OptimizationRequest, SingletSpec, SystemConfiguration


def test_valid_plano_convex():
    spec = SingletSpec(lens_type="plano_convex", radius_2_mm=-75, center_thickness_mm=4, diameter_mm=25)
    assert spec.radius_1_mm is None


@pytest.mark.parametrize("diameter", [0.9, 201])
def test_diameter_boundaries(diameter):
    with pytest.raises(ValidationError):
        SingletSpec(lens_type="bi_convex", radius_1_mm=50, radius_2_mm=-50, center_thickness_mm=4, diameter_mm=diameter)


def test_invalid_lens_type():
    with pytest.raises(ValidationError):
        SingletSpec(lens_type="meniscus", radius_1_mm=50, radius_2_mm=-50, center_thickness_mm=4, diameter_mm=25)


def test_invalid_wavelength():
    with pytest.raises(ValidationError):
        SystemConfiguration(wavelengths_um=[0.1], entrance_pupil_diameter_mm=10)


def test_invalid_mtf_frequency():
    with pytest.raises(ValidationError):
        MTFRequest(frequencies_lp_per_mm=[501])


def test_optimization_whitelist():
    with pytest.raises(ValidationError):
        OptimizationRequest(target_efl_mm=75, variable_names=["glass"])
