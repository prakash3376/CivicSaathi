"""A stand-in for the language model's API that always fails the same way, for fault injection.

    python scripts/stub_provider.py [--port 9999] [--status 503] [--retry-after 3] [--delay 0]

Start the API with ``GEMINI_API_KEY=anything GEMINI_BASE_URL=http://127.0.0.1:9999`` and every
question meets the failure chosen here: the citizen should see the matching official passages, the
rest of the site should carry on, and the admin page should name the cause. ``--delay`` makes it
answer slowly (seconds) to see the time limit at work. It listens on 127.0.0.1 only and answers
nothing but that error.
"""

import argparse
import http.server
import json
import time


def serve(port: int, status: int, retry_after: int | None, delay: float) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def _fail(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            if length:
                self.rfile.read(length)  # the question is read and thrown away, never kept
            time.sleep(delay)
            body = json.dumps(
                {"error": {"code": status, "message": "stub: injected failure", "status": "STUB"}}
            ).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            if retry_after is not None:
                self.send_header("retry-after", str(retry_after))
            self.end_headers()
            self.wfile.write(body)

        do_POST = do_GET = _fail

        def log_message(self, format: str, *args: object) -> None:
            return  # nothing is logged: not even the path

    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--status", type=int, default=503)
    parser.add_argument("--retry-after", type=int)
    parser.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()
    serve(args.port, args.status, args.retry_after, args.delay)


if __name__ == "__main__":
    main()
