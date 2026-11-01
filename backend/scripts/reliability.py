"""The release gate: runs every check there is and says, plainly, what it did and did not prove.

    python scripts/reliability.py                  backend + frontend checks (about 4 minutes)
    python scripts/reliability.py --browser        also the two real-Chrome journeys
    python scripts/reliability.py --live           also the tests that call Gemini and the internet
    python scripts/reliability.py --only provider  only steps whose id or group contains "provider"

Each step is a real command whose exit status decides its result; nothing is assumed. Statuses:

  PASS        ran, and everything held
  FAIL        ran, and something did not
  DEGRADED    ran and passed, but printed findings a person should read (warnings)
  BLOCKED     could not run here (a tool, a browser or a key is missing): says which
  NOT TESTED  not run in this mode, or no test exists: says why

The verdict is "NOT RELEASE-READY" if any P0 or P1 step FAILED, "INCOMPLETE" if none failed but a
P0 or P1 step was BLOCKED or NOT TESTED (it cannot be called ready on what was not checked), and
"RELEASE-READY" only when every P0 and P1 step passed. A feature this application does not have
(uploads, accounts, a SQL database) is listed as ``N/A`` and NOT TESTED with the reason: it does
not count for or against the verdict, and it is never shown as passing. "Release-ready" means the
checks listed here held; the NOT TESTED lines are what they did not cover. A report is written to
``storage/reliability/report-<time>.json`` and ``.md``. Run it with the backend's virtual
environment's Python, from ``backend/``. It never touches a running server: the browser stage
starts its own on free ports and stops only those.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
REPORTS = BACKEND / "storage" / "reliability"
PYTHON = sys.executable
PYTEST = [PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"]

PASS, FAIL, DEGRADED, BLOCKED, NOT_TESTED = "PASS", "FAIL", "DEGRADED", "BLOCKED", "NOT TESTED"
KEY_SHAPE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


@dataclass
class Result:
    id: str
    group: str
    title: str
    priority: str
    status: str
    detail: str = ""
    seconds: float = 0.0
    output_tail: list[str] = field(default_factory=list)


@dataclass
class Step:
    id: str
    group: str
    title: str
    priority: str  # P0 serious harm, P1 critical journey, P2 important, P3 minor
    command: list[str] | None = None
    cwd: Path = BACKEND
    timeout: int = 900
    blocked: Callable[[], str | None] = lambda: None  # a reason it cannot run here, or None
    skip: str | None = None  # a reason it is not run in this mode
    classify: Callable[[int, str], tuple[str, str]] | None = None


def tail_of(output: str, lines: int = 12) -> list[str]:
    return [line for line in output.splitlines() if line.strip()][-lines:]


RESULT_LINE = re.compile(
    r"\d+ (passed|failed)|All checks passed|no issues found|already formatted|Prettier code style"
    r"|built in|Found \d+ (warnings?|errors?)|\d+ problems",
    re.IGNORECASE,
)


def summary(output: str) -> str:
    """The line that says how it went: the last result-looking line, else the last line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if RESULT_LINE.search(line):
            return line
    return lines[-1] if lines else ""


def by_exit(code: int, output: str) -> tuple[str, str]:
    line = summary(output)
    if code == 0 and (not line or line.startswith(">")):
        line = "exit status 0, nothing reported"  # a quiet tool: npm's own echo is not a result
    return (PASS if code == 0 else FAIL), line


def pytest_result(code: int, output: str) -> tuple[str, str]:
    line = summary(output)
    if code == 0 and re.search(r"\b0 passed\b|no tests ran", line):
        return FAIL, f"no test ran: {line}"  # a gate that ran nothing has proved nothing
    return (PASS if code == 0 else FAIL), line


def warnings_count(code: int, output: str) -> tuple[str, str]:
    line = summary(output)
    match = re.search(r"(\d+) warnings?", line)
    if code != 0:
        return FAIL, line
    return (DEGRADED if match and int(match.group(1)) else PASS), line


def need_index() -> str | None:
    return None if (BACKEND / "storage" / "parsed").is_dir() else "no index: run `ingest` first"


def need_npm() -> str | None:
    return None if shutil.which("npm") else "npm is not installed"


def need_frontend_deps() -> str | None:
    if not (FRONTEND / "node_modules").is_dir():
        return "frontend dependencies are not installed: run `npm ci` in frontend/"
    return need_npm()


def chrome_path(args: argparse.Namespace) -> str | None:
    candidates = [
        args.chrome,
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    return next((c for c in candidates if c and Path(c).exists()), None)


def node_modules(args: argparse.Namespace) -> Path | None:
    for candidate in (
        args.node_modules,
        os.environ.get("E2E_NODE_MODULES"),
        str(FRONTEND / "node_modules"),
    ):
        if candidate and (Path(candidate) / "puppeteer-core").is_dir():
            return Path(candidate)
    return None


def pytest_files(*names: str) -> list[str]:
    return [*PYTEST, *(f"tests/{name}" for name in names)]


def scan_for_secrets() -> tuple[str, str]:
    """A key-shaped string in the source is a leaked key: the one check that needs no command."""
    found: list[str] = []
    for folder in (
        BACKEND / "app",
        BACKEND / "scripts",
        BACKEND / "tests",
        FRONTEND / "src",
        ROOT / "docs",
    ):
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".md",
                ".toml",
                ".json",
            }:
                continue
            try:
                if KEY_SHAPE.search(path.read_text(encoding="utf-8", errors="ignore")):
                    found.append(str(path.relative_to(ROOT)))
            except OSError:
                continue
    for env_file in (BACKEND / ".env.example", FRONTEND / ".env.example"):
        if env_file.exists() and KEY_SHAPE.search(env_file.read_text(encoding="utf-8")):
            found.append(str(env_file.relative_to(ROOT)))
    return (
        (FAIL, "key-shaped text in: " + ", ".join(found)) if found else (PASS, "no key-shaped text")
    )


def plan(args: argparse.Namespace) -> list[Step]:
    npm = shutil.which("npm") or "npm"
    chrome = chrome_path(args)
    modules = node_modules(args)
    browser_skip = None if args.browser else "run with --browser (starts its own app on free ports)"
    browser_block = (
        "Chrome was not found: pass --chrome PATH"
        if args.browser and not chrome
        else "puppeteer-core and axe-core were not found: `npm install --no-save puppeteer-core "
        "axe-core` somewhere and pass --node-modules DIR"
        if args.browser and not modules
        else None
    )
    live_skip = None if args.live else "run with --live (calls Gemini and the internet)"
    return [
        Step("secrets", "security", "No API key or token in the source", "P0"),
        Step(
            "lint",
            "backend",
            "Backend lint and formatting",
            "P2",
            [PYTHON, "-m", "ruff", "check", "."],
        ),
        Step(
            "format",
            "backend",
            "Backend formatting",
            "P3",
            [PYTHON, "-m", "ruff", "format", "--check", "."],
        ),
        Step("types", "backend", "Backend types (mypy)", "P2", [PYTHON, "-m", "mypy"]),
        Step(
            "provider",
            "ai-failure",
            "The model fails every way the provider can (20 modes)",
            "P0",
            pytest_files("test_provider_outage.py", "test_gemini.py", "test_resilient.py"),
            classify=pytest_result,
        ),
        Step(
            "grounding",
            "ai-failure",
            "Nothing unverified reaches a citizen",
            "P0",
            pytest_files(
                "test_assistant_service.py",
                "test_grounding_verify.py",
                "test_grounding_numbers.py",
                "test_citations.py",
                "test_injection.py",
            ),
            classify=pytest_result,
        ),
        Step(
            "eligibility",
            "correctness",
            "Eligibility invariants over generated and hostile input",
            "P0",
            pytest_files(
                "test_eligibility_engine.py",
                "test_eligibility_properties.py",
                "test_eligibility_service.py",
            ),
            classify=pytest_result,
        ),
        Step(
            "index-safety",
            "data-integrity",
            "Index backup, restore, lock and interrupted ingestion",
            "P0",
            pytest_files(
                "test_index_safety.py",
                "test_cli_index_safety.py",
                "test_ingest_interruptions.py",
                "test_store.py",
                "test_store_cache.py",
                "test_jobs.py",
            ),
            classify=pytest_result,
        ),
        Step(
            "consistency",
            "data-integrity",
            "Records agree with each other",
            "P0",
            pytest_files("test_consistency.py", "test_catalogue.py"),
            classify=pytest_result,
        ),
        Step(
            "security",
            "security",
            "Abuse, injection, oversized requests, admin access",
            "P0",
            pytest_files(
                "test_abuse.py",
                "test_injection.py",
                "test_body_limit.py",
                "test_admin.py",
                "test_rate_limit.py",
                "test_errors.py",
                "test_middleware.py",
            ),
            classify=pytest_result,
        ),
        Step(
            "backend",
            "backend",
            "The whole backend test suite",
            "P1",
            PYTEST,
            classify=pytest_result,
        ),
        Step(
            "schemes-check",
            "data-accuracy",
            "Every scheme rule's quote is in its document",
            "P0",
            [PYTHON, "-m", "app.cli", "schemes-check"],
            blocked=need_index,
        ),
        Step(
            "catalogue-check",
            "data-accuracy",
            "Every programme and budget quote is in its document",
            "P0",
            [PYTHON, "-m", "app.cli", "catalogue-check"],
            blocked=need_index,
            classify=warnings_count,
        ),
        Step(
            "index-check",
            "data-integrity",
            "Index, records and registry agree (read-only)",
            "P1",
            [PYTHON, "-m", "app.cli", "index-check"],
            blocked=need_index,
            classify=warnings_count,
        ),
        Step(
            "fe-lint",
            "frontend",
            "Frontend lint (accessibility rules included)",
            "P2",
            [npm, "run", "lint"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "fe-types",
            "frontend",
            "Frontend types",
            "P2",
            [npm, "run", "typecheck"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "fe-format",
            "frontend",
            "Frontend formatting",
            "P3",
            [npm, "run", "format:check"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "fe-reliability",
            "frontend",
            "Errors, offline, retries, double submits, stale answers",
            "P1",
            [npm, "run", "test:reliability"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "fe-tests",
            "frontend",
            "The whole frontend test suite (three languages)",
            "P1",
            [npm, "test"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "fe-build",
            "frontend",
            "Production build",
            "P1",
            [npm, "run", "build"],
            FRONTEND,
            blocked=need_frontend_deps,
        ),
        Step(
            "journey",
            "browser",
            "Citizen journey in real Chrome, model failing",
            "P1",
            skip=browser_skip,
            blocked=lambda: browser_block,
        ),
        Step(
            "resilience",
            "browser",
            "Offline, slow network, reload, double click in real Chrome",
            "P1",
            skip=browser_skip,
            blocked=lambda: browser_block,
        ),
        Step(
            "live",
            "ai-live",
            "Real Gemini, real documents, real internet",
            "P2",
            [*PYTEST, "-m", "live"],
            skip=live_skip,
            classify=pytest_result,
        ),
        Step(
            "uploads",
            "not-applicable",
            "Document upload, quarantine and processing states",
            "N/A",
            skip="no upload feature: documents enter only by a person adding a registry entry",
        ),
        Step(
            "accounts",
            "not-applicable",
            "Multi-tab and multi-device edits of saved user data",
            "N/A",
            skip="no accounts or saved server-side user data exist: answers live in memory only",
        ),
        Step(
            "sql",
            "not-applicable",
            "Database transactions, migrations and constraints",
            "N/A",
            skip="no SQL database: records are checked files, the index is derived data",
        ),
        Step(
            "deploy-restore",
            "not-tested",
            "Restoring a backup on a second, separate machine",
            "P2",
            skip="the restore is tested in this repository's tests, not on another machine",
        ),
        Step(
            "load-restart",
            "not-tested",
            "Behaviour under load while the index is rebuilt",
            "P2",
            skip="the load test (scripts/loadtest.py) was not run with a concurrent rebuild",
        ),
    ]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":  # a Windows child (npx, uvicorn's reloader) outlives terminate()
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def wait_for(url: str, seconds: int = 120) -> bool:
    import urllib.request

    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except OSError:
            time.sleep(1)
    return False


def run_browser(
    args: argparse.Namespace, wanted: list[Step]
) -> dict[str, tuple[str, str, list[str]]]:
    """Start the stub provider, API and front end on free ports, run the journeys, stop them."""
    chrome, modules = chrome_path(args), node_modules(args)
    assert chrome
    assert modules
    stub_port, api_port, web_port = free_port(), free_port(), free_port()
    started: list[subprocess.Popen[bytes]] = []
    results: dict[str, tuple[str, str, list[str]]] = {}
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        started.append(
            subprocess.Popen(
                [PYTHON, str(BACKEND / "scripts" / "stub_provider.py"), "--port", str(stub_port)],
                **quiet,
            )
        )
        started.append(
            subprocess.Popen(
                [
                    PYTHON,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--port",
                    str(api_port),
                    "--log-level",
                    "warning",
                ],
                cwd=BACKEND,
                **quiet,
                env={
                    **os.environ,
                    "GEMINI_API_KEY": "stub-key",
                    "ASSISTANT_RATE_LIMIT_PER_MINUTE": "0",
                    "GEMINI_BASE_URL": f"http://127.0.0.1:{stub_port}",
                    "LLM_BREAKER_THRESHOLD": "50",
                },
            )
        )
        started.append(
            subprocess.Popen(
                [shutil.which("npx") or "npx", "vite", "--port", str(web_port), "--strictPort"],
                cwd=FRONTEND,
                **quiet,
                env={**os.environ, "API_PROXY_TARGET": f"http://127.0.0.1:{api_port}"},
            )
        )
        if not wait_for(f"http://127.0.0.1:{api_port}/api/v1/health"):
            reason = "the API did not start in 2 minutes"
            return {s.id: (BLOCKED, reason, []) for s in wanted}
        if not wait_for(f"http://localhost:{web_port}/"):
            reason = "the front end did not start in 2 minutes"
            return {s.id: (BLOCKED, reason, []) for s in wanted}
        for step in wanted:
            results[step.id] = run_script(step, chrome, modules, web_port)
    finally:
        for process in reversed(started):
            stop(process)
    return results


def run_script(step: Step, chrome: str, modules: Path, web_port: int) -> tuple[str, str, list[str]]:
    """Run one journey script with Node.

    Node's ES modules look for packages beside the script and ignore ``NODE_PATH``, so unless the
    packages are in ``frontend/node_modules`` the script is copied next to the ``node_modules``
    that has them, run there, and the copy removed.
    """
    source = FRONTEND / "e2e" / f"{step.id}.mjs"
    in_place = modules.resolve() == (FRONTEND / "node_modules").resolve()
    folder = None if in_place else modules.parent / f".e2e-run-{os.getpid()}"
    script = source
    if folder is not None:
        folder.mkdir(exist_ok=True)
        script = folder / source.name
        shutil.copyfile(source, script)
    try:
        done = subprocess.run(
            ["node", str(script), f"http://localhost:{web_port}", chrome],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=script.parent,
            timeout=step.timeout,
        )
    except subprocess.TimeoutExpired:
        return FAIL, f"did not finish in {step.timeout} s", []
    finally:
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
    output = done.stdout + done.stderr
    if "ERR_MODULE_NOT_FOUND" in output:
        return BLOCKED, "a package the journey needs (puppeteer-core, axe-core) was not found", []
    return (PASS if done.returncode == 0 else FAIL), summary(output), tail_of(output, 14)


def execute(step: Step) -> Result:
    result = Result(step.id, step.group, step.title, step.priority, NOT_TESTED)
    if step.skip:
        result.detail = step.skip
        return result
    reason = step.blocked()
    if reason:
        result.status, result.detail = BLOCKED, reason
        return result
    started = time.time()
    if step.command is None:  # an inline check
        result.status, result.detail = scan_for_secrets()
    else:
        try:
            done = subprocess.run(
                step.command,
                cwd=step.cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=step.timeout,
            )
        except subprocess.TimeoutExpired:
            result.status, result.detail = FAIL, f"did not finish in {step.timeout} s"
        except OSError as error:
            result.status, result.detail = BLOCKED, f"could not start: {type(error).__name__}"
        else:
            output = done.stdout + done.stderr
            result.status, result.detail = (step.classify or by_exit)(done.returncode, output)
            result.output_tail = tail_of(output) if result.status in {FAIL, DEGRADED} else []
    result.seconds = round(time.time() - started, 1)
    return result


def verdict(results: list[Result]) -> str:
    critical = [r for r in results if r.priority in {"P0", "P1"}]
    if any(r.status == FAIL for r in critical):
        return "NOT RELEASE-READY"
    if any(r.status in {BLOCKED, NOT_TESTED} for r in critical):
        return "INCOMPLETE"
    return "RELEASE-READY"


def write_report(results: list[Result], overall: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    counts = {
        s: sum(r.status == s for r in results) for s in (PASS, FAIL, DEGRADED, BLOCKED, NOT_TESTED)
    }
    body = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "verdict": overall,
        "counts": counts,
        "python": sys.version.split()[0],
        "results": [asdict(r) for r in results],
    }
    path = REPORTS / f"report-{stamp}.json"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    lines = [
        f"# Reliability report {stamp}",
        "",
        f"**Verdict: {overall}**",
        "",
        " · ".join(f"{k}: {v}" for k, v in counts.items()),
        "",
        "| Status | Priority | Step | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {r.status} | {r.priority} | {r.title} | {r.detail.replace('|', '/')} |" for r in results
    ]
    path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):  # a Windows console's code page cannot print every tool's output
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--browser", action="store_true", help="also run the real-Chrome journeys")
    parser.add_argument("--live", action="store_true", help="also run the tests that call Gemini")
    parser.add_argument("--only", help="run only steps whose id or group contains this")
    parser.add_argument("--chrome", help="path to Chrome (or set CHROME_PATH)")
    parser.add_argument(
        "--node-modules", help="a node_modules folder holding puppeteer-core and axe-core"
    )
    args = parser.parse_args()

    steps = plan(args)
    if args.only:
        steps = [s for s in steps if args.only in s.id or args.only in s.group]
    results: list[Result] = []
    runnable_browser = [s for s in steps if s.group == "browser" and not s.skip and not s.blocked()]
    browser_done = run_browser(args, runnable_browser) if runnable_browser else {}
    row = "{:<11} {:<4} {:<64} {}"
    print(row.format("STATUS", "PRI", "STEP", "DETAIL"))
    for step in steps:
        if step.id in browser_done:
            status, detail, tail = browser_done[step.id]
            result = Result(
                step.id,
                step.group,
                step.title,
                step.priority,
                status,
                detail,
                output_tail=tail if status == FAIL else [],
            )
        else:
            result = execute(step)
        results.append(result)
        print(
            row.format(result.status, result.priority, result.title[:64], result.detail[:90]),
            flush=True,
        )
        for line in result.output_tail:
            print("      | " + line[:160])
    overall = verdict(results)
    path = write_report(results, overall)
    print(f"\nVerdict: {overall}\nReport: {path} (and .md)")
    return 0 if overall == "RELEASE-READY" else 1


if __name__ == "__main__":
    sys.exit(main())
