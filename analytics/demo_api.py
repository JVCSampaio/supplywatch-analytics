"""Local reproducible source API. Run python -m analytics.demo_api."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def make_handler(path, page_size=100):
    records = json.loads(Path(path).read_text(encoding="utf-8"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/events":
                self.send_error(404)
                return
            try:
                page = int(parse_qs(parsed.query).get("page", ["1"])[0])
                if page < 1:
                    raise ValueError()
            except ValueError:
                self.send_error(400)
                return
            start = (page - 1) * page_size
            payload = {
                "items": records[start : start + page_size],
                "next_page": page + 1 if start + page_size < len(records) else None,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "data/source/events.json"
    print(f"Synthetic source API: http://127.0.0.1:{args.port}/events", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(source)).serve_forever()
