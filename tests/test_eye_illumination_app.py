from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile
import io

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "experiments" / "eye_illumination" / "app"
sys.path.insert(0, str(APP_DIR))

from server import create_server  # noqa: E402
from service import ExperimentService, RequestError  # noqa: E402


@pytest.fixture(scope="module")
def service() -> ExperimentService:
    return ExperimentService()


def test_public_config_exposes_only_fixed_grid(service: ExperimentService) -> None:
    config = service.public_config()
    assert config["case_count"] == 252
    assert config["source_demands_D"] == [60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0]
    assert config["eyes"][0]["label"] == "30–45 日龄小鸡"
    assert config["eyes"][0]["fixed_focal_lengths_mm"] == [7.5, 8.0, 8.5]
    assert config["eyes"][1]["fixed_focal_lengths_mm"] == [13.5, 15.1, 16.7]
    assert config["eyes"][2]["fixed_focal_lengths_mm"] == [12.8, 14.75, 16.7]
    assert config["validation_scope"]["real_experiment"] == "NOT_READY"


def test_public_config_distinguishes_ppt_ranges_from_model_assumptions(service: ExperimentService) -> None:
    config = service.public_config()
    chick = config["eyes"][0]["range_parameters"]
    child = config["eyes"][1]["range_parameters"]
    assert chick["effective_focal_length_mm"]["minimum"] == 7.5
    assert chick["effective_focal_length_mm"]["maximum"] == 8.5
    assert chick["axial_length_mm"]["minimum"] == 10.5
    assert chick["axial_length_mm"]["maximum"] == 12.5
    assert "PPT slide 1" in chick["axial_length_mm"]["provenance"]
    assert "Model sensitivity assumption" in child["axial_length_mm"]["provenance"]
    assert len(chick["reference_component_parameters"]) == 4


def test_calculate_matches_validated_adult_case(service: ExperimentService) -> None:
    result = service.calculate(
        {"eye_id": "adult_18y", "focal_length_mm": 16.7, "pupil_diameter_mm": 5, "source_demand_D": 60}
    )
    assert result["source_distance_mm"] == pytest.approx(16.6666666667)
    assert result["conservative_source_diameter_mm"] == pytest.approx(10.3885111134)
    assert result["geometric_min_source_diameter_mm"] == pytest.approx(0.9335227095)
    assert result["maximum_source_pupil_ray_angle_deg"] > 10.0
    assert result["working_f_number"] == pytest.approx(16.7 / 5.0)
    assert result["paraxial_screening_pass"] is False
    assert result["real_experiment_readiness"] == "BLOCKED_CALIBRATION_REQUIRED"
    assert "accommodation_D" not in result


def test_complete_sweep_has_every_requested_case(service: ExperimentService) -> None:
    rows = service.sweep()
    assert len(rows) == 252
    assert {row["eye_id"] for row in rows} == {"chick_30_45d", "child_6y", "adult_18y"}
    assert {row["source_demand_D"] for row in rows} == {60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0}
    assert all(row["conservative_source_diameter_mm"] >= row["geometric_min_source_diameter_mm"] for row in rows)


def test_service_rejects_continuous_or_out_of_grid_inputs(service: ExperimentService) -> None:
    with pytest.raises(RequestError, match="focal_length_mm must be one of"):
        service.calculate(
            {"eye_id": "adult_18y", "focal_length_mm": 15.0, "pupil_diameter_mm": 5, "source_demand_D": 60}
        )
    with pytest.raises(RequestError, match="source_demand_D must be one of"):
        service.calculate(
            {"eye_id": "adult_18y", "focal_length_mm": 16.7, "pupil_diameter_mm": 5, "source_demand_D": 65}
        )


def test_range_mode_accepts_independent_in_range_values(service: ExperimentService) -> None:
    result = service.calculate(
        {
            "mode": "range",
            "eye_id": "chick_30_45d",
            "focal_length_mm": 7.83,
            "axial_length_mm": 12.2,
            "pupil_diameter_mm": 2.7,
            "source_demand_D": 85,
            "external_lens_power_D": 0,
        }
    )
    assert result["mode"] == "range"
    assert result["effective_focal_length_mm"] == 7.83
    assert result["axial_length_mm"] == 12.2
    assert result["pupil_diameter_mm"] == 2.7
    assert result["source_demand_D"] == 85
    assert result["conservative_source_diameter_mm"] == pytest.approx(5.9866957071)
    assert "accommodation_D" not in result


def test_range_mode_rejects_out_of_range_and_invalid_lens_order(service: ExperimentService) -> None:
    base = {
        "mode": "range",
        "eye_id": "adult_18y",
        "focal_length_mm": 14.75,
        "axial_length_mm": 23.6,
        "pupil_diameter_mm": 5.0,
        "source_demand_D": 80,
        "external_lens_power_D": 0,
    }
    with pytest.raises(RequestError, match="focal_length_mm must be between 12.8 and 16.7"):
        service.calculate({**base, "focal_length_mm": 17.0})
    with pytest.raises(RequestError, match="外镜顶点距 12 mm 必须小于光源距离"):
        service.calculate({**base, "source_demand_D": 120, "external_lens_power_D": -1})


def test_range_sensitivity_and_three_level_grid(service: ExperimentService) -> None:
    request = {
        "mode": "range",
        "eye_id": "chick_30_45d",
        "focal_length_mm": 7.9,
        "axial_length_mm": 11.7,
        "pupil_diameter_mm": 2.8,
        "source_demand_D": 85,
        "external_lens_power_D": 0,
    }
    sensitivity = service.range_sensitivity({**request, "vary_by": "axial_length_mm"})
    assert sensitivity["series_values"] == [10.5, 11.7, 12.5]
    assert sensitivity["row_count"] == 21
    assert sensitivity["skipped_count"] == 0
    grid = service.range_grid(request)
    assert grid["requested_count"] == 126
    assert grid["row_count"] == 126
    assert grid["skipped_count"] == 0


def test_http_server_serves_app_and_calculation() -> None:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base}/api/health", timeout=5) as response:
            assert json.load(response)["status"] == "ok"
        with urlopen(f"{base}/readiness.json", timeout=5) as response:
            assert json.load(response)["real_experiment_readiness_status"] == "NOT_READY"
        with urlopen(f"{base}/readiness.md", timeout=5) as response:
            readiness_markdown = response.read().decode("utf-8")
            assert response.headers["Content-Type"] == "text/markdown; charset=utf-8"
            assert "真实实验适用性验证报告" in readiness_markdown
        with urlopen(f"{base}/report.html", timeout=5) as response:
            report_html = response.read().decode("utf-8")
            assert response.headers["Content-Type"] == "text/html"
            assert "'unsafe-inline'" in response.headers["Content-Security-Policy"]
            assert "真实实验状态为" in report_html
            assert "NOT READY" in report_html
        with urlopen(f"{base}/api/sweep.csv", timeout=5) as response:
            csv_body = response.read().decode("utf-8-sig")
            assert response.headers["Content-Disposition"] == 'attachment; filename="eye_illumination_252_cases.csv"'
        assert len(csv_body.splitlines()) == 253
        assert "accommodation_D" not in csv_body.splitlines()[0]
        range_query = (
            "mode=range&eye_id=chick_30_45d&focal_length_mm=7.9&axial_length_mm=11.7&"
            "pupil_diameter_mm=2.8&source_demand_D=85&external_lens_power_D=0&vary_by=axial_length_mm"
        )
        with urlopen(f"{base}/api/range-sensitivity.csv?{range_query}", timeout=5) as response:
            range_csv = response.read().decode("utf-8-sig")
            assert "eye_range_sensitivity_21_cases.csv" in response.headers["Content-Disposition"]
        assert len(range_csv.splitlines()) == 22
        request = Request(
            f"{base}/api/calculate",
            data=json.dumps(
                {"eye_id": "chick_30_45d", "focal_length_mm": 8.5, "pupil_diameter_mm": 3.5, "source_demand_D": 120}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            result = json.load(response)
        assert result["conservative_source_diameter_mm"] == pytest.approx(6.2538132512)

        batch_request = Request(
            f"{base}/api/zemax-batch",
            data=json.dumps({"cases": [{
                "mode": "baseline", "eye_id": "chick_30_45d", "focal_length_mm": 8.5,
                "pupil_diameter_mm": 3.5, "source_demand_D": 120,
            }]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(batch_request, timeout=5) as response:
            package = response.read()
            assert response.headers["Content-Type"] == "application/zip"
            assert response.headers["X-Zemax-Case-Count"] == "1"
            assert response.headers["X-Zemax-Batch-Id"].startswith("eye-zemax-")
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            assert "manifest.json" in archive.namelist()
            assert "scripts/ZosApiEyeBatch.cs" in archive.namelist()

        with urlopen(f"{base}/api/zemax/preflight", timeout=5) as response:
            preflight = json.load(response)
        assert preflight["license_status"] == "NOT_TESTED"
        assert "api_dlls" in preflight

        unconfirmed_job = Request(
            f"{base}/api/zemax/jobs",
            data=json.dumps({
                "mode": "connection_test",
                "cases": [{
                    "mode": "baseline", "eye_id": "chick_30_45d", "focal_length_mm": 8.5,
                    "pupil_diameter_mm": 3.5, "source_demand_D": 120,
                }],
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(unconfirmed_job, timeout=5)
        assert error.value.code == 400
        assert "明确确认" in error.value.read().decode("utf-8")

        invalid = Request(
            f"{base}/api/calculate",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(invalid, timeout=5)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
