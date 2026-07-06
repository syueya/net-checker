#!/usr/bin/env python3
from http.server import ThreadingHTTPServer

from net_checker.config import ensure_config
from net_checker.env import load_settings
from net_checker.server import make_handler


def main():
    settings = load_settings()
    ensure_config(settings.config_path)
    handler = make_handler(settings.config_path, settings.static_dir)
    server = ThreadingHTTPServer((settings.host, settings.port), handler)
    print(f"Net checker web UI listening on http://{settings.host}:{settings.port}")
    print(f"Config path: {settings.config_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
