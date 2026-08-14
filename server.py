"""Safe stdio MCP server for constrained OpticStudio operations."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from backend.mock_backend import MockOpticStudioBackend
from backend.protocol import OpticStudioBackend
from config import Settings
from models import MTFRequest, OptimizationRequest, SingletSpec, SpotRequest, SystemConfiguration


settings = Settings.from_env()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("zemax_mcp")


def build_backend() -> OpticStudioBackend:
    if settings.backend == "mock":
        return MockOpticStudioBackend(settings)
    from backend.zosapi_backend import ZOSAPIBackend
    return ZOSAPIBackend(settings)


backend = build_backend()
mcp = FastMCP("zemax-opticstudio")


def audited(tool_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            summary = {key: ("<redacted>" if "path" in key.lower() else value) for key, value in kwargs.items()}
            logger.info("tool=%s status=start params=%s", tool_name, summary)
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.exception("tool=%s status=error exception=%s", tool_name, type(exc).__name__)
                raise
            logger.info("tool=%s status=success", tool_name)
            return result
        return wrapper
    return decorator


@mcp.tool()
@audited("zemax_health")
def zemax_health() -> dict:
    """Report backend connection, workspace, version, and capability status."""
    return backend.health_check()


@mcp.tool()
@audited("new_sequential_design")
def new_sequential_design() -> dict:
    """Start a fresh unsaved sequential design without writing a file."""
    return backend.new_sequential_system()


@mcp.tool()
@audited("create_singlet")
def create_singlet(
    lens_type: str,
    center_thickness_mm: float,
    diameter_mm: float,
    glass: str = "N-BK7",
    radius_1_mm: float | None = None,
    radius_2_mm: float | None = None,
) -> dict:
    """Create a validated plano/bi convex/concave singlet in memory."""
    spec = SingletSpec(lens_type=lens_type, glass=glass, radius_1_mm=radius_1_mm, radius_2_mm=radius_2_mm, center_thickness_mm=center_thickness_mm, diameter_mm=diameter_mm)
    return backend.create_singlet(spec)


@mcp.tool()
@audited("configure_system")
def configure_system(
    entrance_pupil_diameter_mm: float,
    wavelengths_um: list[float] | None = None,
    field_angles_deg: list[float] | None = None,
    image_distance_mm: float | None = None,
) -> dict:
    """Configure wavelengths in um, fields in degrees, aperture and optional image distance in mm."""
    payload: dict[str, Any] = {"entrance_pupil_diameter_mm": entrance_pupil_diameter_mm, "image_distance_mm": image_distance_mm}
    if wavelengths_um is not None: payload["wavelengths_um"] = wavelengths_um
    if field_angles_deg is not None: payload["field_angles_deg"] = field_angles_deg
    return backend.set_system_configuration(SystemConfiguration(**payload))


@mcp.tool()
@audited("quick_focus_preview")
def quick_focus_preview() -> dict:
    """Calculate a suggested image distance without changing the design."""
    return backend.quick_focus_preview()


@mcp.tool()
@audited("apply_quick_focus")
def apply_quick_focus(confirm: bool = False) -> dict:
    """Preview focus, and apply it only when confirm is explicitly true."""
    if not confirm:
        return {**backend.quick_focus_preview(), "confirmation_required": True}
    return backend.apply_quick_focus()


@mcp.tool()
@audited("paraxial_summary")
def paraxial_summary() -> dict:
    """Return read-only EFL, BFL, F-number, status, and assumptions."""
    return backend.get_paraxial_summary()


@mcp.tool()
@audited("spot_diagram")
def spot_diagram(field_deg: float = 0, wavelength_um: float = 0.5461) -> dict:
    """Return structured spot radii for one field and wavelength."""
    return backend.spot_diagram(SpotRequest(field_deg=field_deg, wavelength_um=wavelength_um))


@mcp.tool()
@audited("mtf")
def mtf(field_deg: float = 0, wavelength_um: float = 0.5461, frequencies_lp_per_mm: list[float] | None = None) -> dict:
    """Return structured sagittal and tangential MTF samples."""
    payload: dict[str, Any] = {"field_deg": field_deg, "wavelength_um": wavelength_um}
    if frequencies_lp_per_mm is not None: payload["frequencies_lp_per_mm"] = frequencies_lp_per_mm
    return backend.mtf(MTFRequest(**payload))


@mcp.tool()
@audited("preview_optimization")
def preview_optimization(target_efl_mm: float, variable_names: list[str], max_iterations: int = 50) -> dict:
    """Validate and preview an EFL optimization without modifying the design."""
    return backend.preview_optimization(OptimizationRequest(target_efl_mm=target_efl_mm, variable_names=variable_names, max_iterations=max_iterations))


@mcp.tool()
@audited("run_optimization")
def run_optimization(target_efl_mm: float, variable_names: list[str], max_iterations: int = 50, confirm: bool = False) -> dict:
    """Run a bounded optimization only after explicit confirmation."""
    request = OptimizationRequest(target_efl_mm=target_efl_mm, variable_names=variable_names, max_iterations=max_iterations)
    if not confirm:
        return {**backend.preview_optimization(request), "confirmation_required": True}
    return backend.run_optimization(request)


@mcp.tool()
@audited("preview_save_design")
def preview_save_design(relative_path: str) -> dict:
    """Validate a new .ZOS destination within the approved workspace without writing."""
    return backend.preview_save(relative_path)


@mcp.tool()
@audited("save_design")
def save_design(relative_path: str, confirm: bool = False) -> dict:
    """Save a new .ZOS design only after confirmation; never overwrite."""
    preview = backend.preview_save(relative_path)
    if preview["exists"]:
        raise FileExistsError("Refusing to overwrite an existing design")
    if not confirm:
        return {**preview, "confirmation_required": True}
    return backend.save_design(relative_path)


@mcp.tool()
@audited("close_zemax_session")
def close_zemax_session(confirm: bool = False) -> dict:
    """Close only a standalone session, and only after explicit confirmation."""
    if settings.connect_mode == "extension":
        return {"closed": False, "reason": "Extension mode never closes the user's OpticStudio instance"}
    if not confirm:
        return {"closed": False, "confirmation_required": True}
    backend.close()
    return {"closed": True}


if __name__ == "__main__":
    mcp.run(transport="stdio")
