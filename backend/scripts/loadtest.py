"""A modest load test of the public API: many visitors, each browsing the way a person does.

    python scripts/loadtest.py [--users 20] [--seconds 20] [--base-url http://127.0.0.1:8000]

Without ``--base-url`` it starts the real server on a local port and stops it afterwards. Each
simulated visitor loops for ``--seconds``: open the home page's data (schemes, sources, budget),
look at one programme, run an eligibility check, pause 0.2 to 0.6 seconds like a reader, and repeat.
The assistant is **not** asked: each question is a call to a paid, rate-limited model, and a load
test of it would spend quota and measure Google, not this code. Its latency is measured by
``python -m app.cli eval --answer`` instead.

It is a test of one machine, with its own limits: a handful of CPU cores, a client that shares the
machine with the server, and the loopback network. Read the figures as "this process on this
machine", not as a promise about a deployment. Never point it at a service you do not run.

Reports requests, errors, p50 / p95 / p99 per endpoint, throughput, and the server's memory before
and after if ``psutil`` is installed. Written to ``storage/benchmarks/load-<time>.json``.
"""

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def call(
    base: str,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    etag: str | None = None,
) -> tuple[int, float, str | None]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept-Encoding": "gzip", "Content-Type": "application/json"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
            status, tag = response.status, response.headers.get("ETag")
    except urllib.error.HTTPError as error:
        error.read()
        status, tag = error.code, None
    except OSError:
        status, tag = 0, None  # refused, reset or timed out
    return status, (time.perf_counter() - started) * 1000, tag


def visitor(base: str, track: str, until: float, record: list[tuple[str, int, float]]) -> None:
    rng = random.Random()
    tags: dict[str, str] = {}
    while time.monotonic() < until:
        for method, path, body in (
            ("GET", "/api/v1/schemes", None),
            ("GET", "/api/v1/sources", None),
            ("GET", "/api/v1/budget", None),
            ("GET", "/api/v1/schemes/pm-kisan", None),
            ("POST", "/api/v1/schemes/svmcm/eligibility", {"track": track, "answers": {}}),
        ):
            # A browser sends back the hash it was given: the second visit is a revalidation.
            status, ms, tag = call(base, method, path, body, tags.get(path))
            if tag:
                tags[path] = tag
            record.append((f"{method} {path}", status, ms))
            if time.monotonic() >= until:
                return
        time.sleep(rng.uniform(0.2, 0.6))


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[int(share * (len(ordered) - 1))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--base-url")
    args = parser.parse_args()

    server = None
    base = args.base_url
    if base is None:
        env = {**os.environ, "LOG_LEVEL": "WARNING", "ACCESS_LOG": "false"}
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                "8120",
                "--log-level",
                "warning",
            ],
            cwd=BACKEND,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base = "http://127.0.0.1:8120"
    try:
        for _ in range(120):
            if call(base, "GET", "/api/v1/health")[0] == 200:
                break
            time.sleep(0.5)
        else:
            raise SystemExit("the server did not start")
        # Warm up, and learn a valid track for the eligibility check.
        for path in ("/api/v1/schemes", "/api/v1/sources", "/api/v1/budget"):
            call(base, "GET", path)
        with urllib.request.urlopen(base + "/api/v1/schemes/svmcm") as response:
            track = json.loads(response.read())["tracks"][0]["id"]

        memory_before = rss(server.pid) if server else None
        record: list[tuple[str, int, float]] = []
        lock = threading.Lock()
        until = time.monotonic() + args.seconds
        started = time.monotonic()

        def run() -> None:
            mine: list[tuple[str, int, float]] = []
            visitor(base, track, until, mine)
            with lock:
                record.extend(mine)

        threads = [threading.Thread(target=run) for _ in range(args.users)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        elapsed = time.monotonic() - started
        memory_after = rss(server.pid) if server else None
    finally:
        if server:
            server.terminate()
            server.wait(timeout=20)

    rows: dict[str, dict[str, object]] = {}
    for name in sorted({name for name, *_ in record}):
        mine = [(status, ms) for n, status, ms in record if n == name]
        times = [ms for status, ms in mine if status in (200, 304)]
        rows[name] = {
            "requests": len(mine),
            "errors": sum(1 for status, _ in mine if status not in (200, 304)),
            "not_modified": sum(1 for status, _ in mine if status == 304),
            "p50_ms": round(statistics.median(times), 1) if times else None,
            "p95_ms": round(percentile(times, 0.95), 1) if times else None,
            "p99_ms": round(percentile(times, 0.99), 1) if times else None,
        }
    total = len(record)
    errors = sum(1 for _n, status, _ms in record if status not in (200, 304))
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "users": args.users,
        "seconds": round(elapsed, 1),
        "requests": total,
        "errors": errors,
        "error_rate": round(errors / total, 4) if total else None,
        "requests_per_second": round(total / elapsed, 1),
        "server_memory_mb": {"before": memory_before, "after": memory_after},
        "machine": {"cpus": os.cpu_count(), "python": sys.version.split()[0]},
        "endpoints": rows,
    }
    out = BACKEND / "storage" / "benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"load-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"{args.users} visitors for {report['seconds']} s: {total} requests, {errors} errors, "
        f"{report['requests_per_second']} requests/s, "
        f"server memory {memory_before} -> {memory_after} MB\n"
    )
    row = "{:<42} {:>8} {:>7} {:>8} {:>8} {:>8}"
    print(row.format("endpoint", "requests", "errors", "p50 ms", "p95 ms", "p99 ms"))
    for name, r in rows.items():
        print(row.format(name, r["requests"], r["errors"], r["p50_ms"], r["p95_ms"], r["p99_ms"]))
    print(f"\nwritten: {path}")


def rss(pid: int) -> float | None:
    """The server's resident memory in MB, if psutil is available."""
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return None
    total = psutil.Process(pid).memory_info().rss
    for child in psutil.Process(pid).children(recursive=True):
        total += child.memory_info().rss
    return round(total / 1_048_576, 1)


if __name__ == "__main__":
    main()
