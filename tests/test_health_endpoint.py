from __future__ import annotations

import http.client
import json
import threading
from http.server import HTTPServer

from ralph_gold import __version__
from ralph_gold.health import make_health_handler


def test_health_endpoint_returns_status_and_version() -> None:
    handler = make_health_handler(__version__)
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        conn.request("GET", "/health")
        response = conn.getresponse()
        body = response.read().decode("utf-8")

        assert response.status == 200
        payload = json.loads(body)
        assert payload.get("status") == "ok"
        assert payload.get("version") == __version__
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
