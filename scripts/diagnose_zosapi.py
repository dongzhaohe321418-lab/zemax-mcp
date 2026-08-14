"""Read-only diagnostics for locating a local ZOS-API installation."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def main() -> int:
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"64-bit: {sys.maxsize > 2**32}")
    configured = os.getenv("ZEMAX_ZOSAPI_NETHELPER_DLL")
    if configured:
        candidate = Path(configured).expanduser()
        print(f"Configured NetHelper: {candidate} (exists={candidate.is_file()})")
    else:
        print("ZEMAX_ZOSAPI_NETHELPER_DLL is not set")
    try:
        import clr  # type: ignore[import-not-found]  # noqa: F401
        print("pythonnet: available")
    except Exception as exc:
        print(f"pythonnet: unavailable ({type(exc).__name__}: {exc})")
    print("Consult the OpticStudio Programming/ZOS-API Python samples for the exact DLL and connection sequence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
