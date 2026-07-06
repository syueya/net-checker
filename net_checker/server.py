import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from .checks import run_checks
from .config import clone_default_config, load_config, normalize_config, save_config


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_request_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return None
    raw = handler.rfile.read(length)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def make_handler(config_path, static_dir):
    config_path = Path(config_path)
    static_dir = Path(static_dir)
    static_dir_resolved = static_dir.resolve()

    class NetCheckerHandler(BaseHTTPRequestHandler):
        server_version = "NetChecker/1.0"

        def log_message(self, fmt, *args):
            print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

        def do_GET(self):
            if self.path == "/api/config":
                json_response(self, 200, load_config(config_path))
                return
            self.serve_static()

        def do_PUT(self):
            if self.path != "/api/config":
                json_response(self, 404, {"error": "Not found"})
                return
            try:
                payload = read_request_json(self) or {}
                config = save_config(config_path, payload)
                json_response(self, 200, {"ok": True, "config": config})
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if self.path == "/api/check":
                try:
                    payload = read_request_json(self)
                    config = normalize_config(payload) if payload else load_config(config_path)
                    json_response(self, 200, run_checks(config))
                except Exception as exc:
                    json_response(self, 400, {"error": str(exc)})
                return

            if self.path == "/api/reset":
                config = save_config(config_path, clone_default_config())
                json_response(self, 200, {"ok": True, "config": config})
                return

            json_response(self, 404, {"error": "Not found"})

        def serve_static(self):
            request_path = self.path.split("?", 1)[0]
            if request_path in {"", "/"}:
                request_path = "/index.html"

            relative = request_path.lstrip("/")
            file_path = (static_dir / relative).resolve()
            try:
                file_path.relative_to(static_dir_resolved)
            except ValueError:
                json_response(self, 403, {"error": "Forbidden"})
                return

            if not file_path.exists() or not file_path.is_file():
                json_response(self, 404, {"error": "Not found"})
                return

            content = file_path.read_bytes()
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            if file_path.suffix == ".js":
                content_type = "application/javascript; charset=utf-8"
            elif file_path.suffix in {".html", ".css", ".svg"}:
                content_type = f"{content_type}; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return NetCheckerHandler
