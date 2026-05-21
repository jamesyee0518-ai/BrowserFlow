import http.server
import json
import os
import uuid
import time
import threading
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
SITE_DIR = os.path.dirname(os.path.abspath(__file__))

lock = threading.Lock()

def load_results():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_results(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/results":
            self._api_get_results()
        elif parsed.path == "/results" or parsed.path == "/results.html":
            self.path = "/results.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/results":
            self._api_post_results()
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/results/"):
            rid = parsed.path.split("/")[-1]
            self._api_delete_result(rid)
        else:
            self.send_error(404)

    def _api_get_results(self):
        with lock:
            data = load_results()
        self._json_response(200, data)

    def _api_post_results(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid JSON"})
            return

        record = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile_name": payload.get("profile_name", "Unknown"),
            "score": payload.get("score", 0),
            "summary": payload.get("summary", {}),
            "categories": payload.get("categories", []),
            "captcha_results": payload.get("captcha_results", {}),
            "interaction_results": payload.get("interaction_results", {}),
        }

        with lock:
            data = load_results()
            data.append(record)
            save_results(data)

        self._json_response(201, record)

    def _api_delete_result(self, rid):
        with lock:
            data = load_results()
            data = [r for r in data if r["id"] != rid]
            save_results(data)
        self._json_response(200, {"deleted": rid})

    def _json_response(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()

    server = http.server.HTTPServer((args.bind, args.port), Handler)
    print(f"  CloakBrowser Detection Test Server")
    print(f"  Listening on http://{args.bind}:{args.port}")
    print(f"  Detection page:  http://<your-ip>:{args.port}")
    print(f"  Results page:    http://<your-ip>:{args.port}/results.html")
    print(f"  API endpoint:    http://<your-ip>:{args.port}/api/results")
    print(f"  Press Ctrl+C to stop")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()

if __name__ == "__main__":
    main()
