"""Prepare (and optionally upload) the folder that Hugging Face builds the container from.

    python deploy/huggingface/stage.py                       # only prepare the folder, print it
    python deploy/huggingface/stage.py --upload OWNER/NAME   # prepare it and push it to the Space

The upload needs the ``huggingface_hub`` package and a token that can write to the Space, in the
``HF_TOKEN`` environment variable (never on the command line, so it stays out of shell history).

What goes in: the frontend sources, the backend ``app`` and ``data``, the dependency pins, the
Dockerfile and the Space's README. What stays out, always: ``.env`` files and anything that looks
like a key, ``node_modules``, ``.venv``, tests, caches, and every part of ``storage`` except the
document index (``storage/chroma``), which the container needs.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

SKIP_NAMES = {
    "node_modules",
    "dist",
    "dist-ssr",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "e2e",
    "tests",
    ".git",
}
SKIP_SUFFIXES = {".pyc", ".log", ".tsbuildinfo"}
KEY_SHAPED = re.compile(r"AIza[0-9A-Za-z_\-]{30,}|hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}")
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".json", ".toml", ".md", ".txt", ".html", ".css"}


def _ignore(directory: str, names: list[str]) -> list[str]:
    skipped = []
    for name in names:
        path = Path(directory) / name
        if name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES or name.startswith(".env"):
            skipped.append(name)
    return skipped


def stage(target: Path) -> None:
    """Fill ``target`` (an empty folder) with what the container is built from."""
    shutil.copytree(ROOT / "frontend", target / "frontend", ignore=_ignore)
    backend = target / "backend"
    backend.mkdir()
    for name in ("requirements.txt", "constraints.txt", "pyproject.toml"):
        shutil.copy2(ROOT / "backend" / name, backend / name)
    shutil.copytree(ROOT / "backend" / "app", backend / "app", ignore=_ignore)
    shutil.copytree(ROOT / "backend" / "data", backend / "data", ignore=_ignore)

    chroma = ROOT / "backend" / "storage" / "chroma"
    if not chroma.is_dir():
        raise SystemExit("backend/storage/chroma is missing: run `python -m app.cli ingest` first")
    (backend / "storage").mkdir()
    shutil.copytree(chroma, backend / "storage" / "chroma")

    shutil.copy2(HERE / "Dockerfile", target / "Dockerfile")
    shutil.copy2(HERE / "README.md", target / "README.md")
    _refuse_secrets(target)


def _refuse_secrets(target: Path) -> None:
    """Stop before anything leaves this machine if a key or an .env file got in."""
    found: list[str] = []
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(target).as_posix()
        if path.name.startswith(".env") and path.name != ".env.example":
            found.append(relative)
        elif path.suffix in TEXT_SUFFIXES and path.stat().st_size < 2_000_000:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if KEY_SHAPED.search(text):
                found.append(relative)
    if found:
        raise SystemExit("refusing to continue, secret-looking content in: " + ", ".join(found))


def upload(folder: Path, repo_id: str) -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("set HF_TOKEN (a token with write access) in the environment first")
    from huggingface_hub import HfApi  # imported here: only needed to upload

    api = HfApi(token=token)
    api.upload_folder(
        folder_path=str(folder),
        repo_id=repo_id,
        repo_type="space",
        commit_message="Deploy CivicSaathi",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--upload", metavar="OWNER/NAME", help="push the folder to this Space")
    parser.add_argument("--out", type=Path, help="prepare the folder here (must not exist)")
    args = parser.parse_args()

    target = args.out or Path(tempfile.mkdtemp(prefix="civicsaathi-space-"))
    if args.out:
        if target.exists():
            raise SystemExit(f"{target} already exists")
        target.mkdir(parents=True)
    stage(target)
    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1e6
    print(f"prepared {target} ({size:.0f} MB, no secrets found)")
    if args.upload:
        upload(target, args.upload)
        print(f"uploaded to https://huggingface.co/spaces/{args.upload}")
    sys.exit(0)


if __name__ == "__main__":
    main()
