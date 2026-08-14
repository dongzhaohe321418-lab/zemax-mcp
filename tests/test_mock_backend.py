from pathlib import Path

import pytest

from backend.mock_backend import MockOpticStudioBackend
from config import Settings
from models import OptimizationRequest, SingletSpec, SpotRequest, SystemConfiguration


def backend(tmp_path: Path) -> MockOpticStudioBackend:
    return MockOpticStudioBackend(Settings(workspace=tmp_path))


def test_positive_and_negative_focal_lengths(tmp_path):
    instance = backend(tmp_path)
    instance.create_singlet(SingletSpec(lens_type="bi_convex", radius_1_mm=50, radius_2_mm=-50, center_thickness_mm=4, diameter_mm=25))
    assert instance.get_paraxial_summary()["efl_mm"] > 0
    instance.create_singlet(SingletSpec(lens_type="bi_concave", radius_1_mm=-50, radius_2_mm=50, center_thickness_mm=4, diameter_mm=25))
    assert instance.get_paraxial_summary()["efl_mm"] < 0


def test_analysis_is_structured_and_estimated(tmp_path):
    instance = backend(tmp_path)
    instance.create_singlet(SingletSpec(lens_type="bi_convex", radius_1_mm=50, radius_2_mm=-50, center_thickness_mm=4, diameter_mm=25))
    instance.set_system_configuration(SystemConfiguration(entrance_pupil_diameter_mm=10))
    result = instance.spot_diagram(SpotRequest())
    assert result["rms_radius_mm"] > 0
    assert result["result_kind"] == "estimated"


def test_save_preview_and_no_overwrite(tmp_path):
    instance = backend(tmp_path)
    assert instance.preview_save("design.ZOS")["will_write"] is False
    first = instance.save_design("design.ZOS")
    assert first["saved"] is True
    with pytest.raises(FileExistsError):
        instance.save_design("design.ZOS")


def test_mock_optimization_does_not_fake_success(tmp_path):
    result = backend(tmp_path).run_optimization(OptimizationRequest(target_efl_mm=75, variable_names=["radius_1_mm"]))
    assert result["supported"] is False
