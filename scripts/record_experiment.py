"""Create an immutable, versionable experiment record from a JSON payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment_id", help="lowercase identifier, e.g. exp-001-bk7-focus")
    parser.add_argument("input_json", type=Path, help="JSON containing inputs, outputs, observations, and artifact paths")
    parser.add_argument("--runs-dir", type=Path, default=Path("experiments/runs"))
    args = parser.parse_args()
    if not ID_PATTERN.fullmatch(args.experiment_id):
        parser.error("experiment_id must be 3-64 lowercase letters, numbers, underscores, or hyphens")
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        parser.error("input JSON must be an object")
    target = args.runs_dir / f"{args.experiment_id}.json"
    if target.exists():
        parser.error(f"refusing to overwrite immutable record: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "experiment_id": args.experiment_id,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        **payload,
    }
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
