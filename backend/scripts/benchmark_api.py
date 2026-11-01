"""Measure the API with the optimisations off and on, against the real data and index.

    python scripts/benchmark_api.py [--requests 100] [--concurrency 8]

It starts the real server twice on local ports (`uvicorn app.main:app`), once with the three
switches off (``CACHE_ENABLED=false COMPRESS_RESPONSES=false ACCESS_LOG=false``: the behaviour
before the performance work) and once with the defaults, and asks both the same questions in the
same order. Nothing is mocked and the assistant (which costs a model call) is not asked: this is the
public, read-only API that every page of the site uses.

For each endpoint it reports, per variant:

  p50 / p95    milliseconds for a request answered in full, one after another
  bytes        what crossed the wire (the client says it accepts gzip in both variants)
  revalidate   a repeat request that sends the ETag it was given, as a browser does (the old
               variant sends no ETag, so every repeat is a full answer)
  concurrent   p50 / p95 and errors with ``--concurrency`` clients asking at once

A server is only ever started on 127.0.0.1, with a fresh process per variant, a warm-up before
measuring, and the machine as it is: close other work for clean numbers. Results are written to
``storage/benchmarks/api-<time>.json`` and printed as a table for docs/BENCHMARKS.md.
"""

import argparse
import concurrent.futures
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ENDPOINTS = (
    "/api/v1/health",
    "/api/v1/schemes",
    "/api/v1/schemes/pm-kisan",
    "/api/v1/budget",
    "/api/v1/sources",
)
VARIANTS = {
    "before": {"CACHE_ENABLED": "false", "COMPRESS_RESPONSES": "false", "ACCESS_LOG": "false"},
    "after": {"CACHE_ENABLED": "true", "COMPRESS_RESPONSES": "true", "ACCESS_LOG": "true"},
}


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[int(share * (len(ordered) - 1))]


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, int, float, str | None]:
    """(status, bytes on the wire, milliseconds, etag)."""
    request = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", **(headers or {})})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            status, etag = response.status, response.headers.get("ETag")
    except urllib.error.HTTPError as error:
        body, status, etag = error.read(), error.code, None
    return status, len(body), (time.perf_counter() - started) * 1000, etag


def start(variant: str, port: int) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        **VARIANTS[variant],
        "LOG_LEVEL": "WARNING",
        "ASSISTANT_RATE_LIMIT_PER_MINUTE": "0",
    }
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_ready(base: str) -> None:
    for _ in range(120):
        try:
            if get(f"{base}/api/v1/health")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(0.5)
    raise SystemExit("the server did not start")


def measure(base: str, path: str, requests: int, concurrency: int) -> dict[str, object]:
    url = base + path
    for _ in range(3):  # warm-up: the first call loads the data and the index
        get(url)
    times, sizes = [], []
    etag = None
    for _ in range(requests):
        status, size, ms, etag = get(url)
        assert status == 200, f"{path} answered {status}"
        times.append(ms)
        sizes.append(size)
    again = [get(url, {"If-None-Match": etag} if etag else None) for _ in range(requests)]
    with concurrent.futures.ThreadPoolExecutor(concurrency) as pool:
        crowd = list(pool.map(lambda _n: get(url), range(requests)))
    crowd_times = [ms for status, _size, ms, _etag in crowd if status == 200]
    return {
        "p50_ms": round(statistics.median(times), 1),
        "p95_ms": round(percentile(times, 0.95), 1),
        "bytes": round(statistics.mean(sizes)),
        "revalidate_p50_ms": round(statistics.median(ms for _s, _b, ms, _e in again), 1),
        "revalidate_bytes": round(statistics.mean(size for _s, size, _m, _e in again)),
        "revalidate_status": sorted({status for status, *_ in again}),
        "concurrent_p50_ms": round(statistics.median(crowd_times), 1),
        "concurrent_p95_ms": round(percentile(crowd_times, 0.95), 1),
        "concurrent_errors": sum(1 for status, *_ in crowd if status != 200),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--variants",
        default="before,after",
        help="which to run (the old behaviour is slow on /sources: it takes minutes)",
    )
    args = parser.parse_args()

    results: dict[str, dict[str, object]] = {}
    chosen = [v for v in args.variants.split(",") if v in VARIANTS]
    for index, variant in enumerate(chosen):
        port = 8110 + index
        server = start(variant, port)
        try:
            base = f"http://127.0.0.1:{port}"
            wait_ready(base)
            results[variant] = {
                path: measure(base, path, args.requests, args.concurrency) for path in ENDPOINTS
            }
        finally:
            server.terminate()
            server.wait(timeout=20)

    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "requests": args.requests,
        "concurrency": args.concurrency,
        "machine": {"python": sys.version.split()[0], "cpus": os.cpu_count()},
        "results": results,
    }
    out = BACKEND / "storage" / "benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"api-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n{args.requests} requests per endpoint, {args.concurrency} concurrent clients\n")
    row = "{:<28} {:>9} {:>9} {:>9} {:>9} {:>11} {:>11}"
    print(
        row.format("endpoint", "p50 ms", "p95 ms", "bytes", "conc p95", "reval ms", "reval bytes")
    )
    for path_ in ENDPOINTS:
        for variant in chosen:
            r = results[variant][path_]
            print(
                row.format(
                    f"{path_.removeprefix('/api/v1')} [{variant}]",
                    r["p50_ms"],  # type: ignore[index]
                    r["p95_ms"],  # type: ignore[index]
                    r["bytes"],  # type: ignore[index]
                    r["concurrent_p95_ms"],  # type: ignore[index]
                    r["revalidate_p50_ms"],  # type: ignore[index]
                    r["revalidate_bytes"],  # type: ignore[index]
                )
            )
    print(f"\nwritten: {path}")


if __name__ == "__main__":
    main()
