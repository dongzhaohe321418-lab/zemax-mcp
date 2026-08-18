"""Local HTTP server for the fixed-focal posterior-pole experiment app."""

from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse
import webbrowser

try:
    from .service import ExperimentService, RequestError
    from .zemax_batch import build_batch_package
except ImportError:  # Direct execution from launch_app.ps1.
    from service import ExperimentService, RequestError
    from zemax_batch import build_batch_package

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
EXPERIMENT_DIR = APP_DIR.parent
ARTIFACTS = {
    "/report.pdf": EXPERIMENT_DIR / "report" / "latex" / "eye_illumination_experiment_report.pdf",
    "/results.csv": EXPERIMENT_DIR / "results" / "fixed_focal_source_sweep.csv",
    "/validation.json": EXPERIMENT_DIR / "results" / "validation_report.json",
    "/zemax-guide.md": EXPERIMENT_DIR / "ZEMAX_CONNECTION_GUIDE.md",
}
STATIC_FILES = {
    "/": STATIC_DIR / "index.html",
    "/index.html": STATIC_DIR / "index.html",
    "/styles.css": STATIC_DIR / "styles.css",
    "/app.js": STATIC_DIR / "app.js",
    "/favicon.svg": STATIC_DIR / "favicon.svg",
}


class ExperimentHandler(BaseHTTPRequestHandler):
    service: ExperimentService
    server_version = "EyeIlluminationLab/1.0"

    def _headers(
        self,
        content_type: str,
        length: int,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'",
        )
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._headers("application/json; charset=utf-8", len(body), status)
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".csv", ".json"}:
            content_type += "; charset=utf-8"
        self._headers(content_type, len(body))
        self.wfile.write(body)

    def _download_json(self, payload: dict[str, Any], filename: str) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._headers(
            "application/json; charset=utf-8",
            len(body),
            extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
        self.wfile.write(body)

    def _download_csv(self, rows: list[dict[str, Any]], filename: str) -> None:
        stream = io.StringIO(newline="")
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        body = ("\ufeff" + stream.getvalue()).encode("utf-8")
        self._headers(
            "text/csv; charset=utf-8",
            len(body),
            extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
        self.wfile.write(body)

    def _download_bytes(
        self,
        body: bytes,
        filename: str,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        headers = {"Content-Disposition": f'attachment; filename="{filename}"', **(extra_headers or {})}
        self._headers(content_type, len(body), extra_headers=headers)
        self.wfile.write(body)

    def _request_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise RequestError("invalid Content-Length") from exc
        if length > 1_000_000:
            raise RequestError("request body is too large")
        if length == 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise RequestError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        if path == "/api/health":
            self._json({"status": "ok", "experiment_id": self.service.config["experiment_id"]})
        elif path == "/api/config":
            self._json(self.service.public_config())
        elif path == "/api/case.json":
            try:
                result = self.service.calculate(query)
                self._download_json(result, f"eye_case_{result['eye_id']}_{result['source_demand_D']:g}D.json")
            except RequestError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/sweep.csv":
            try:
                rows = self.service.sweep(query)
                self._download_csv(rows, f"eye_illumination_{len(rows)}_cases.csv")
            except RequestError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/range-grid.csv":
            try:
                result = self.service.range_grid(query)
                self._download_csv(result["rows"], f"eye_range_grid_{result['row_count']}_cases.csv")
            except RequestError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path == "/api/range-sensitivity.csv":
            try:
                result = self.service.range_sensitivity(query)
                self._download_csv(result["rows"], f"eye_range_sensitivity_{result['row_count']}_cases.csv")
            except RequestError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        elif path in STATIC_FILES:
            self._file(STATIC_FILES[path])
        elif path in ARTIFACTS:
            self._file(ARTIFACTS[path])
        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            payload = self._request_json()
            if path == "/api/calculate":
                self._json(self.service.calculate(payload))
            elif path == "/api/sweep":
                rows = self.service.sweep(payload)
                self._json({"row_count": len(rows), "rows": rows})
            elif path == "/api/range-sensitivity":
                self._json(self.service.range_sensitivity(payload))
            elif path == "/api/range-grid":
                self._json(self.service.range_grid(payload))
            elif path == "/api/zemax-batch":
                rows = self.service.zemax_batch_rows(payload)
                try:
                    package = build_batch_package(rows)
                except ValueError as exc:
                    raise RequestError(str(exc)) from exc
                self._download_bytes(
                    package.content,
                    package.filename,
                    "application/zip",
                    {
                        "X-Zemax-Batch-Id": package.batch_id,
                        "X-Content-SHA256": package.sha256,
                        "X-Zemax-Case-Count": str(package.case_count),
                    },
                )
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except RequestError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    service = ExperimentService()

    class BoundHandler(ExperimentHandler):
        pass

    BoundHandler.service = service
    return ThreadingHTTPServer((host, port), BoundHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the application in the default browser")
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}/"
    print(f"Posterior-pole eye parameter experiment app: {url}")
    print("Press Ctrl+C to stop.")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping application.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
