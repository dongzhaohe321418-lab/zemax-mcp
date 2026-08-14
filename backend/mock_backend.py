"""Deterministic in-memory backend for testing without OpticStudio."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from models import MTFRequest, OptimizationRequest, SingletSpec, SpotRequest, SystemConfiguration


REFRACTIVE_INDICES = {"N-BK7": 1.5168, "N-SF11": 1.7847, "F_SILICA": 1.4585}


@dataclass
class DesignState:
    mode: str = "sequential"
    lens: SingletSpec | None = None
    configuration: SystemConfiguration | None = None
    image_distance_mm: float | None = None


class MockOpticStudioBackend:
    """Provides physically interpretable thin-lens estimates, not ray-trace truth."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = DesignState()

    def health_check(self) -> dict:
        return {
            "backend": "mock",
            "connected": True,
            "workspace": str(self.settings.workspace),
            "opticstudio_version": None,
            "capabilities": {"spot": "estimated", "mtf": "estimated", "optimization": "estimated"},
        }

    def new_sequential_system(self) -> dict:
        self.state = DesignState()
        return {"created": True, "mode": "sequential", "file_written": False}

    def create_singlet(self, spec: SingletSpec) -> dict:
        if spec.glass.upper() not in REFRACTIVE_INDICES:
            raise ValueError(f"Mock glass catalog does not contain {spec.glass!r}")
        self.state.lens = spec
        surfaces = [
            {"number": 0, "role": "object", "radius_mm": None},
            {"number": 1, "role": "front", "radius_mm": spec.radius_1_mm, "glass": spec.glass},
            {"number": 2, "role": "back", "radius_mm": spec.radius_2_mm, "thickness_mm": spec.center_thickness_mm},
            {"number": 3, "role": "image", "radius_mm": None},
        ]
        return {"lens_type": spec.lens_type, "input": spec.model_dump(), "surfaces": surfaces, "file_written": False}

    def set_system_configuration(self, config: SystemConfiguration) -> dict:
        self.state.configuration = config
        self.state.image_distance_mm = config.image_distance_mm
        return {"configuration": config.model_dump(), "file_written": False}

    def _require_lens(self) -> SingletSpec:
        if self.state.lens is None:
            raise RuntimeError("Create a singlet before requesting an analysis")
        return self.state.lens

    def _efl(self) -> float:
        lens = self._require_lens()
        n = REFRACTIVE_INDICES[lens.glass.upper()]
        inv_r1 = 0.0 if lens.radius_1_mm is None else 1.0 / lens.radius_1_mm
        inv_r2 = 0.0 if lens.radius_2_mm is None else 1.0 / lens.radius_2_mm
        power = (n - 1) * (
            inv_r1 - inv_r2 + ((n - 1) * lens.center_thickness_mm * inv_r1 * inv_r2 / n)
        )
        if abs(power) < 1e-12:
            raise RuntimeError("Lens power is zero; EFL is undefined")
        return 1.0 / power

    def quick_focus_preview(self) -> dict:
        efl = self._efl()
        bfl = efl - self._require_lens().center_thickness_mm / 2
        return {
            "suggested_image_distance_mm": bfl,
            "efl_mm": efl,
            "bfl_mm": bfl,
            "method": "thick lensmaker estimate",
            "assumptions": ["object at infinity", "paraxial rays", "catalog index at reference wavelength"],
            "design_modified": False,
        }

    def apply_quick_focus(self) -> dict:
        preview = self.quick_focus_preview()
        self.state.image_distance_mm = preview["suggested_image_distance_mm"]
        return {**preview, "applied": True, "design_modified": True}

    def get_paraxial_summary(self) -> dict:
        efl = self._efl()
        lens = self._require_lens()
        aperture = self.state.configuration.entrance_pupil_diameter_mm if self.state.configuration else lens.diameter_mm
        bfl = efl - lens.center_thickness_mm / 2
        return {
            "efl_mm": efl,
            "bfl_mm": bfl,
            "f_number": abs(efl) / aperture,
            "image_distance_mm": self.state.image_distance_mm,
            "model": "estimated",
            "assumptions": ["paraxial approximation", "object at infinity"],
        }

    def spot_diagram(self, request: SpotRequest) -> dict:
        summary = self.get_paraxial_summary()
        lens = self._require_lens()
        fno = max(summary["f_number"], 0.1)
        chromatic = abs(request.wavelength_um - 0.5461) * 0.03 * lens.diameter_mm
        off_axis = abs(request.field_deg) * 0.002 * lens.diameter_mm
        spherical = 0.02 * lens.diameter_mm / (fno * fno)
        rms = math.sqrt(chromatic**2 + off_axis**2 + spherical**2)
        return {
            "rms_radius_mm": rms,
            "geometric_radius_mm": 2.5 * rms,
            "field_deg": request.field_deg,
            "wavelength_um": request.wavelength_um,
            "image_distance_mm": self.state.image_distance_mm,
            "sampling": "deterministic analytic estimate",
            "result_kind": "estimated",
        }

    def mtf(self, request: MTFRequest) -> dict:
        spot = self.spot_diagram(SpotRequest(field_deg=request.field_deg, wavelength_um=request.wavelength_um))
        sigma = max(spot["rms_radius_mm"], 1e-6)
        values = [
            {"frequency_lp_per_mm": frequency, "sagittal": math.exp(-2 * (math.pi * sigma * frequency) ** 2), "tangential": math.exp(-2.2 * (math.pi * sigma * frequency) ** 2)}
            for frequency in request.frequencies_lp_per_mm
        ]
        return {"values": values, "field_deg": request.field_deg, "wavelength_um": request.wavelength_um, "result_kind": "estimated"}

    def preview_optimization(self, request: OptimizationRequest) -> dict:
        return {
            "target": {"metric": "EFL", "value_mm": request.target_efl_mm},
            "variables": request.variable_names,
            "max_iterations": request.max_iterations,
            "bounds": "model validation bounds",
            "estimated_cost": "low" if request.max_iterations <= 50 else "moderate",
            "design_modified": False,
        }

    def run_optimization(self, request: OptimizationRequest) -> dict:
        return {**self.preview_optimization(request), "supported": False, "reason": "Mock optimization never fabricates a solved design; use a controlled parameter sweep."}

    def preview_save(self, relative_path: str) -> dict:
        target = self.settings.resolve_workspace_path(relative_path, suffix=".ZOS")
        return {"absolute_path": str(target), "exists": target.exists(), "will_write": False}

    def save_design(self, relative_path: str) -> dict:
        target = self.settings.resolve_workspace_path(relative_path, suffix=".ZOS")
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing design: {target}")
        if not target.parent.is_dir():
            raise FileNotFoundError("Destination directory must already exist")
        payload = {
            "format": "mock-zemax-design",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": {
                "mode": self.state.mode,
                "lens": self.state.lens.model_dump() if self.state.lens else None,
                "configuration": self.state.configuration.model_dump() if self.state.configuration else None,
                "image_distance_mm": self.state.image_distance_mm,
            },
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"absolute_path": str(target), "saved": True, "mock_format": True}

    def close(self) -> None:
        return None
