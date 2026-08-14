"""Conservative ZOS-API adapter.

Only connection discovery is implemented without guessing version-specific object
names. Operations that require local API verification fail explicitly.
"""

from __future__ import annotations

from config import Settings


class ZOSAPIBackend:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._application = None
        self._system = None
        self._load_runtime()

    def _load_runtime(self) -> None:
        if self.settings.nethelper_dll is None:
            raise RuntimeError(
                "ZEMAX_ZOSAPI_NETHELPER_DLL is required for the verified ZOS-API adapter. "
                "Run scripts/diagnose_zosapi.py and set it to the discovered DLL."
            )
        if not self.settings.nethelper_dll.is_file():
            raise RuntimeError(f"ZOSAPI_NetHelper.dll not found: {self.settings.nethelper_dll}")
        try:
            import clr  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("pythonnet is unavailable; install the 'zosapi' optional dependencies") from exc
        try:
            clr.AddReference(str(self.settings.nethelper_dll))
        except Exception as exc:
            raise RuntimeError(f"Failed to load ZOS-API NetHelper: {type(exc).__name__}: {exc}") from exc
        raise RuntimeError(
            "NetHelper loaded, but this OpticStudio version has not been locally verified. "
            "Adapt the connection sequence using the installed ZOS-API Python sample before enabling live writes."
        )

    def health_check(self) -> dict:
        return {"backend": "zosapi", "connected": self._system is not None, "workspace": str(self.settings.workspace)}

    def _unverified(self, operation: str) -> dict:
        raise NotImplementedError(f"{operation} requires verification against the locally installed ZOS-API samples")

    def new_sequential_system(self) -> dict: return self._unverified("new_sequential_system")
    def create_singlet(self, spec) -> dict: return self._unverified("create_singlet")
    def set_system_configuration(self, config) -> dict: return self._unverified("set_system_configuration")
    def quick_focus_preview(self) -> dict: return self._unverified("quick_focus_preview")
    def apply_quick_focus(self) -> dict: return self._unverified("apply_quick_focus")
    def get_paraxial_summary(self) -> dict: return self._unverified("get_paraxial_summary")
    def spot_diagram(self, request) -> dict: return self._unverified("spot_diagram")
    def mtf(self, request) -> dict: return self._unverified("mtf")
    def preview_optimization(self, request) -> dict: return self._unverified("preview_optimization")
    def run_optimization(self, request) -> dict: return self._unverified("run_optimization")
    def preview_save(self, relative_path: str) -> dict:
        target = self.settings.resolve_workspace_path(relative_path, suffix=".ZOS")
        return {"absolute_path": str(target), "exists": target.exists(), "will_write": False}
    def save_design(self, relative_path: str) -> dict: return self._unverified("save_design")

    def close(self) -> None:
        if self.settings.connect_mode == "standalone" and self._application is not None:
            # TODO: verify CloseApplication for the locally installed OpticStudio release.
            self._application = None
            self._system = None
