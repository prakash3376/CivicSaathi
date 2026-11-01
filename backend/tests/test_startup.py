import subprocess
import sys

from app.core.config import BACKEND_DIR

HEAVY = ("chromadb", "onnxruntime", "google.genai", "tokenizers", "pypdfium2")


def test_starting_the_api_does_not_load_the_assistant_s_heavy_libraries() -> None:
    """They take seconds to import and are needed only from the first question.

    Loading them at start-up would slow every server start and every `--reload`, and a broken
    install of one of them would stop `/health` from answering. The assistant is imported when a
    request first needs it (`app.api.deps.get_assistant_runtime`).
    """
    script = (
        f"import sys, app.main\nprint(sorted(name for name in {HEAVY!r} if name in sys.modules))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=BACKEND_DIR,
    )

    assert result.stdout.strip() == "[]", f"loaded at start-up: {result.stdout.strip()}"
