"""Application service layer for the fixed-focal eye experiment."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

APP_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = APP_DIR.parent
CONFIG_PATH = EXPERIMENT_DIR / "config" / "experiment.json"
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

DISPLAY_LABELS = {
    "chick_30_45d": "30–45 日龄小鸡",
    "child_6y": "6 岁儿童",
    "adult_18y": "18 岁成人",
}

from eye_model import Eye, fixed_focal_source_solution, load_eyes  # noqa: E402


class RequestError(ValueError):
    """Raised when an application request does not match the experiment grid."""


def _json_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


class ExperimentService:
    """Load the immutable experiment definition and calculate requested cases."""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.eyes = load_eyes(self.config)
        self.eyes_by_id = {eye.eye_id: eye for eye in self.eyes}

    @staticmethod
    def _choice(value: Any, choices: tuple[float, ...] | list[float], name: str) -> float:
        if isinstance(value, bool):
            raise RequestError(f"{name} must be numeric")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise RequestError(f"{name} must be numeric") from exc
        for choice in choices:
            if math.isclose(numeric, float(choice), rel_tol=0.0, abs_tol=1e-9):
                return float(choice)
        raise RequestError(f"{name} must be one of {list(choices)}")

    def _eye(self, eye_id: Any) -> Eye:
        try:
            return self.eyes_by_id[str(eye_id)]
        except KeyError as exc:
            raise RequestError(f"unknown eye_id: {eye_id}") from exc

    def public_config(self) -> dict[str, Any]:
        demands = [float(value) for value in self.config["source_demands_D"]]
        case_count = sum(
            len(eye.fixed_effective_focal_lengths_mm) * len(eye.pupil_diameters_mm) * len(demands)
            for eye in self.eyes
        )
        return {
            "experiment_id": self.config["experiment_id"],
            "wavelength_nm": self.config["wavelength_nm"],
            "source_demands_D": demands,
            "case_count": case_count,
            "model": "fixed-focal reduced-angle ABCD",
            "eyes": [
                {
                    "id": eye.eye_id,
                    "label": DISPLAY_LABELS.get(eye.eye_id, eye.label),
                    "fixed_focal_lengths_mm": list(eye.fixed_effective_focal_lengths_mm),
                    "pupil_diameters_mm": list(eye.pupil_diameters_mm),
                    "reported_axial_length_mm": eye.reported_axial_length_mm,
                    "reduced_retina_distance_mm": 1000.0 * eye.reduced_retina_distance_m,
                    "posterior_pole_diameter_mm": eye.posterior_pole_diameter_mm,
                    "image_medium_refractive_index": eye.image_medium_refractive_index,
                }
                for eye in self.eyes
            ],
        }

    def calculate(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        eye = self._eye(request.get("eye_id"))
        focal_mm = self._choice(
            request.get("focal_length_mm"), eye.fixed_effective_focal_lengths_mm, "focal_length_mm"
        )
        pupil_mm = self._choice(request.get("pupil_diameter_mm"), eye.pupil_diameters_mm, "pupil_diameter_mm")
        demand_D = self._choice(request.get("source_demand_D"), self.config["source_demands_D"], "source_demand_D")
        source_distance_m = 1.0 / demand_D
        solution = fixed_focal_source_solution(eye, source_distance_m, focal_mm, pupil_mm)
        result = {
            "experiment_id": self.config["experiment_id"],
            "eye_id": eye.eye_id,
            "eye_label": DISPLAY_LABELS.get(eye.eye_id, eye.label),
            "wavelength_nm": float(self.config["wavelength_nm"]),
            "source_demand_D": demand_D,
            "source_distance_mm": 1000.0 * source_distance_m,
            "reported_axial_length_mm": eye.reported_axial_length_mm,
            "posterior_pole_diameter_mm": eye.posterior_pole_diameter_mm,
            **solution,
        }
        return {key: _json_value(value) for key, value in result.items()}

    def sweep(self, request: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        request = request or {}
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        eyes = self.eyes if request.get("eye_id") in (None, "", "all") else [self._eye(request["eye_id"])]
        rows: list[dict[str, Any]] = []
        for eye in eyes:
            focals = eye.fixed_effective_focal_lengths_mm
            pupils = eye.pupil_diameters_mm
            if request.get("focal_length_mm") is not None:
                focals = (self._choice(request["focal_length_mm"], focals, "focal_length_mm"),)
            if request.get("pupil_diameter_mm") is not None:
                pupils = (self._choice(request["pupil_diameter_mm"], pupils, "pupil_diameter_mm"),)
            for focal_mm in focals:
                for pupil_mm in pupils:
                    for demand_D in self.config["source_demands_D"]:
                        rows.append(
                            self.calculate(
                                {
                                    "eye_id": eye.eye_id,
                                    "focal_length_mm": focal_mm,
                                    "pupil_diameter_mm": pupil_mm,
                                    "source_demand_D": demand_D,
                                }
                            )
                        )
        return rows
