"""Application service layer for baseline and PPT-range eye experiments."""

from __future__ import annotations

from dataclasses import replace
from itertools import product
import json
import math
from pathlib import Path
import sys
from typing import Any

APP_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = APP_DIR.parent
CONFIG_PATH = EXPERIMENT_DIR / "config" / "experiment.json"
RANGE_CONFIG_PATH = APP_DIR / "range_parameters.json"
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

DISPLAY_LABELS = {
    "chick_30_45d": "30–45 日龄小鸡",
    "child_6y": "6 岁儿童",
    "adult_18y": "18 岁成人",
}

from eye_model import Eye, adjustable_source_solution, fixed_focal_source_solution, load_eyes  # noqa: E402


class RequestError(ValueError):
    """Raised when a request falls outside the declared experiment space."""


def _json_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _unique_levels(*values: float) -> list[float]:
    unique: list[float] = []
    for value in values:
        if not any(math.isclose(value, existing, rel_tol=0.0, abs_tol=1e-9) for existing in unique):
            unique.append(float(value))
    return unique


class ExperimentService:
    """Calculate validated fixed-grid cases and manually selected range cases."""

    def __init__(self, config_path: Path = CONFIG_PATH, range_config_path: Path = RANGE_CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.range_config_path = Path(range_config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.range_config = json.loads(self.range_config_path.read_text(encoding="utf-8"))
        self.eyes = load_eyes(self.config)
        self.eyes_by_id = {eye.eye_id: eye for eye in self.eyes}

    @staticmethod
    def _number(value: Any, name: str) -> float:
        if isinstance(value, bool):
            raise RequestError(f"{name} must be numeric")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise RequestError(f"{name} must be numeric") from exc
        if not math.isfinite(numeric):
            raise RequestError(f"{name} must be finite")
        return numeric

    @classmethod
    def _choice(cls, value: Any, choices: tuple[float, ...] | list[float], name: str) -> float:
        numeric = cls._number(value, name)
        for choice in choices:
            if math.isclose(numeric, float(choice), rel_tol=0.0, abs_tol=1e-9):
                return float(choice)
        raise RequestError(f"{name} must be one of {list(choices)}")

    @classmethod
    def _bounded(cls, value: Any, specification: dict[str, Any], name: str) -> float:
        numeric = cls._number(value, name)
        minimum = float(specification["minimum"])
        maximum = float(specification["maximum"])
        if numeric < minimum - 1e-9 or numeric > maximum + 1e-9:
            raise RequestError(f"{name} must be between {minimum:g} and {maximum:g}")
        return min(max(numeric, minimum), maximum)

    def _eye(self, eye_id: Any) -> Eye:
        try:
            return self.eyes_by_id[str(eye_id)]
        except KeyError as exc:
            raise RequestError(f"unknown eye_id: {eye_id}") from exc

    def _range_eye(self, eye_id: str) -> dict[str, Any]:
        try:
            return self.range_config["eyes"][eye_id]
        except KeyError as exc:
            raise RequestError(f"range configuration missing for eye_id: {eye_id}") from exc

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
            "model": "independent-parameter reduced-angle ABCD",
            "modes": ["baseline", "range"],
            "range_explorer": {
                "mode_id": self.range_config["mode_id"],
                "source_demand_D": self.range_config["source_demand_D"],
                "external_lens_powers_D": self.range_config["external_lens_powers_D"],
                "identifiability_note": self.range_config["identifiability_note"],
            },
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
                    "range_parameters": self._range_eye(eye.eye_id),
                }
                for eye in self.eyes
            ],
        }

    def calculate(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        mode = request.get("mode", "baseline")
        if mode == "range":
            return self.calculate_range(request)
        if mode != "baseline":
            raise RequestError("mode must be baseline or range")
        eye = self._eye(request.get("eye_id"))
        focal_mm = self._choice(
            request.get("focal_length_mm"), eye.fixed_effective_focal_lengths_mm, "focal_length_mm"
        )
        pupil_mm = self._choice(request.get("pupil_diameter_mm"), eye.pupil_diameters_mm, "pupil_diameter_mm")
        demand_D = self._choice(request.get("source_demand_D"), self.config["source_demands_D"], "source_demand_D")
        solution = fixed_focal_source_solution(eye, 1.0 / demand_D, focal_mm, pupil_mm)
        return self._result(eye, eye, solution, demand_D, "baseline", 0.0)

    def calculate_range(self, request: dict[str, Any]) -> dict[str, Any]:
        eye = self._eye(request.get("eye_id"))
        ranges = self._range_eye(eye.eye_id)
        focal_mm = self._bounded(
            request.get("focal_length_mm"), ranges["effective_focal_length_mm"], "focal_length_mm"
        )
        axial_mm = self._bounded(request.get("axial_length_mm"), ranges["axial_length_mm"], "axial_length_mm")
        pupil_mm = self._bounded(
            request.get("pupil_diameter_mm"), ranges["pupil_diameter_mm"], "pupil_diameter_mm"
        )
        demand_D = self._bounded(
            request.get("source_demand_D"), self.range_config["source_demand_D"], "source_demand_D"
        )
        external_power_D = self._choice(
            request.get("external_lens_power_D", 0.0),
            self.range_config["external_lens_powers_D"]["values"],
            "external_lens_power_D",
        )
        adjusted_eye = replace(eye, reported_axial_length_mm=axial_mm)
        try:
            solution = adjustable_source_solution(
                adjusted_eye, 1.0 / demand_D, focal_mm, pupil_mm, external_power_D
            )
        except ValueError as exc:
            if external_power_D != 0.0 and "vertex distance" in str(exc):
                source_distance_mm = 1000.0 / demand_D
                raise RequestError(
                    f"外镜顶点距 {eye.external_lens_vertex_distance_mm:g} mm 必须小于光源距离 "
                    f"{source_distance_mm:.2f} mm；请降低物方需求或选择 0 D 外镜"
                ) from exc
            raise RequestError(str(exc)) from exc
        return self._result(eye, adjusted_eye, solution, demand_D, "range", external_power_D)

    def _result(
        self,
        baseline_eye: Eye,
        active_eye: Eye,
        solution: dict[str, Any],
        demand_D: float,
        mode: str,
        external_power_D: float,
    ) -> dict[str, Any]:
        result = {
            "experiment_id": self.config["experiment_id"],
            "mode": mode,
            "eye_id": active_eye.eye_id,
            "eye_label": DISPLAY_LABELS.get(active_eye.eye_id, active_eye.label),
            "wavelength_nm": float(self.config["wavelength_nm"]),
            "source_demand_D": demand_D,
            "source_distance_mm": 1000.0 / demand_D,
            "axial_length_mm": active_eye.reported_axial_length_mm,
            "baseline_axial_length_mm": baseline_eye.reported_axial_length_mm,
            "posterior_pole_diameter_mm": active_eye.posterior_pole_diameter_mm,
            "effective_focal_length_mm": solution["fixed_focal_length_mm"],
            "external_lens_power_D": external_power_D,
            "external_lens_vertex_distance_mm": baseline_eye.external_lens_vertex_distance_mm,
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
            for focal_mm, pupil_mm, demand_D in product(focals, pupils, self.config["source_demands_D"]):
                rows.append(
                    self.calculate(
                        {
                            "mode": "baseline",
                            "eye_id": eye.eye_id,
                            "focal_length_mm": focal_mm,
                            "pupil_diameter_mm": pupil_mm,
                            "source_demand_D": demand_D,
                        }
                    )
                )
        return rows

    def range_sensitivity(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        base = self.calculate_range({**request, "mode": "range"})
        vary_by = str(request.get("vary_by", "focal_length_mm"))
        specifications = {
            "focal_length_mm": "effective_focal_length_mm",
            "axial_length_mm": "axial_length_mm",
            "pupil_diameter_mm": "pupil_diameter_mm",
        }
        if vary_by not in specifications:
            raise RequestError(f"vary_by must be one of {list(specifications)}")
        specification = self._range_eye(base["eye_id"])[specifications[vary_by]]
        result_key = "effective_focal_length_mm" if vary_by == "focal_length_mm" else vary_by
        current_value = float(base[result_key])
        levels = _unique_levels(float(specification["minimum"]), current_value, float(specification["maximum"]))
        rows: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        demand_values = self.range_config["source_demand_D"]["sweep_values"]
        for level, demand_D in product(levels, demand_values):
            case_request = {
                "mode": "range",
                "eye_id": base["eye_id"],
                "focal_length_mm": base["effective_focal_length_mm"],
                "axial_length_mm": base["axial_length_mm"],
                "pupil_diameter_mm": base["pupil_diameter_mm"],
                "source_demand_D": demand_D,
                "external_lens_power_D": base["external_lens_power_D"],
                vary_by: level,
            }
            try:
                row = self.calculate_range(case_request)
                row["series_parameter"] = vary_by
                row["series_value"] = level
                rows.append(row)
            except RequestError as exc:
                skipped.append({"series_value": level, "source_demand_D": demand_D, "reason": str(exc)})
        return {
            "vary_by": vary_by,
            "series_values": levels,
            "row_count": len(rows),
            "skipped_count": len(skipped),
            "rows": rows,
            "skipped": skipped,
        }

    def range_grid(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        base = self.calculate_range({**request, "mode": "range"})
        ranges = self._range_eye(base["eye_id"])
        focal = ranges["effective_focal_length_mm"]
        axial = ranges["axial_length_mm"]
        pupil = ranges["pupil_diameter_mm"]
        focal_levels = _unique_levels(float(focal["minimum"]), float(focal["default"]), float(focal["maximum"]))
        axial_levels = _unique_levels(float(axial["minimum"]), float(axial["default"]), float(axial["maximum"]))
        pupil_levels = _unique_levels(float(pupil["minimum"]), float(pupil["default"]), float(pupil["maximum"]))
        demand_values = self.range_config["source_demand_D"]["sweep_values"]
        rows: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        combinations = list(product(focal_levels, axial_levels, pupil_levels, demand_values))
        for focal_mm, axial_mm, pupil_mm, demand_D in combinations:
            case_request = {
                "mode": "range",
                "eye_id": base["eye_id"],
                "focal_length_mm": focal_mm,
                "axial_length_mm": axial_mm,
                "pupil_diameter_mm": pupil_mm,
                "source_demand_D": demand_D,
                "external_lens_power_D": base["external_lens_power_D"],
            }
            try:
                rows.append(self.calculate_range(case_request))
            except RequestError as exc:
                skipped.append({**case_request, "reason": str(exc)})
        return {
            "requested_count": len(combinations),
            "row_count": len(rows),
            "skipped_count": len(skipped),
            "rows": rows,
            "skipped": skipped,
        }

    def zemax_batch_rows(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        """Recalculate untrusted browser inputs before freezing a Zemax batch."""
        if not isinstance(request, dict):
            raise RequestError("request body must be a JSON object")
        cases = request.get("cases")
        if not isinstance(cases, list) or not cases:
            raise RequestError("cases must be a non-empty array")
        if len(cases) > 1000:
            raise RequestError("Zemax batch is limited to 1000 cases")
        allowed = {
            "mode",
            "eye_id",
            "focal_length_mm",
            "axial_length_mm",
            "pupil_diameter_mm",
            "source_demand_D",
            "external_lens_power_D",
        }
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(cases, start=1):
            if not isinstance(item, dict):
                raise RequestError(f"case {index} must be a JSON object")
            inputs = {key: value for key, value in item.items() if key in allowed}
            try:
                rows.append(self.calculate(inputs))
            except RequestError as exc:
                raise RequestError(f"case {index}: {exc}") from exc
        return rows
