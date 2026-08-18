from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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


def test_calculate_matches_validated_adult_case(service: ExperimentService) -> None:
    result = service.calculate(
        {"eye_id": "adult_18y", "focal_length_mm": 16.7, "pupil_diameter_mm": 5, "source_demand_D": 60}
    )
    assert result["source_distance_mm"] == pytest.approx(16.6666666667)
    assert result["conservative_source_diameter_mm"] == pytest.approx(10.3885111134)
    assert result["geometric_min_source_diameter_mm"] == pytest.approx(0.9335227095)
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


def test_http_server_serves_app_and_calculation() -> None:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base}/api/health", timeout=5) as response:
            assert json.load(response)["status"] == "ok"
        with urlopen(f"{base}/api/sweep.csv", timeout=5) as response:
            csv_body = response.read().decode("utf-8-sig")
            assert response.headers["Content-Disposition"] == 'attachment; filename="eye_illumination_252_cases.csv"'
        assert len(csv_body.splitlines()) == 253
        assert "accommodation_D" not in csv_body.splitlines()[0]
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
