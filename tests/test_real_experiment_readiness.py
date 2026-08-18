from __future__ import annotations

import json
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "eye_illumination"


def test_real_experiment_audit_never_confuses_model_validation_with_release() -> None:
    report = json.loads(
        (EXPERIMENT / "results" / "real_experiment_readiness.json").read_text(encoding="utf-8")
    )
    assert report["calculation_validation_status"] == "VERIFIED_WITHIN_FIRST_ORDER_MODEL"
    assert report["real_experiment_readiness_status"] == "NOT_READY"
    assert report["decision"] == "DO_NOT_USE_AS_FINAL_EXPOSURE_OR_SAFETY_SETTINGS"
    assert report["opticstudio_validation_scope"]["scope"].startswith("Paraxial")
    assert len(report["real_experiment_blockers"]) >= 5


def test_readiness_audit_quantifies_the_model_domain_risk() -> None:
    report = json.loads(
        (EXPERIMENT / "results" / "real_experiment_readiness.json").read_text(encoding="utf-8")
    )
    applicability = report["paraxial_applicability"]
    assert applicability["case_count"] == 252
    assert applicability["cases_above_screening_angle"] == 252
    assert applicability["cases_above_15_deg"] == 252
    assert applicability["cases_below_f_number_4"] == 140
    assert applicability["cases_passing_both_project_screens"] == 0
    assert applicability["minimum_maximum_ray_angle_deg"] > 15.0
    assert applicability["maximum_maximum_ray_angle_deg"] < 38.0


def test_readiness_audit_records_current_official_safety_families() -> None:
    report = json.loads(
        (EXPERIMENT / "results" / "real_experiment_readiness.json").read_text(encoding="utf-8")
    )
    standards = {item["standard"] for item in report["official_safety_references"]}
    assert standards == {"ISO 15004-2:2024", "IEC 62471:2006", "IEC 60825-1:2014"}
    modeling_sources = {item["publisher"] for item in report["official_modeling_references"]}
    assert modeling_sources == {"Ansys"}
    assert len(report["official_modeling_references"]) == 3
