"""Admin CLI entry point.

Only ``doctor`` is implemented so far. The rest of the command surface
(``docs/HANDOVER.md`` section 33) depends on config.py, the archive and the
database, none of which exist yet -- see BATON.md/STATE.md for current phase.

Each doctor check imports its target lazily and catches its own exceptions:
one missing or broken dependency degrades that single row rather than
crashing the whole command, and the command stays runnable in a lightweight
environment (e.g. CI) that hasn't installed the full ML stack.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _main() -> None:
    """bikematch admin CLI. Only ``doctor`` exists so far; see module docstring."""
    # An explicit callback keeps Typer in subcommand mode (`bikematch doctor`)
    # even while there is only one command -- without it, Typer collapses a
    # single-command app so the command name itself becomes an unexpected
    # argument, breaking exactly the invocation the README/Dockerfile use.

_NOT_YET_IMPLEMENTED = [
    "IMAP",
    "outbound email",
    "eBay API",
    "Playwright browser",
    "Facebook profile state",
    "archive write test",
]


def _run_check(name: str, fn: Callable[[], str]) -> bool:
    try:
        detail = fn()
    except Exception as exc:  # one bad check must not crash the rest
        typer.echo(f"[FAIL] {name:<38} {type(exc).__name__}: {exc}")
        return False
    typer.echo(f"[ OK ] {name:<38} {detail}")
    return True


def _check_python() -> str:
    return sys.version.split()[0]


def _check_torch() -> str:
    import torch

    x = torch.nn.functional.normalize(torch.randn(4, 4), dim=1)
    assert abs(float((x * x).sum(dim=1).mean()) - 1.0) < 1e-4, "torch maths wrong"
    return f"{torch.__version__} (cuda_available={torch.cuda.is_available()})"


def _check_faiss() -> str:
    import faiss
    import numpy as np

    idx = faiss.IndexFlatIP(8)
    vec = np.random.rand(1, 8).astype("float32")
    idx.add(vec)
    _, i = idx.search(vec, 1)
    assert i[0][0] == 0, "faiss self-retrieval wrong"
    return faiss.__version__


def _check_sqlalchemy() -> str:
    import sqlalchemy

    return sqlalchemy.__version__


def _check_pillow() -> str:
    import PIL

    return PIL.__version__


def _check_disk_path(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return "does not exist here (expected on the RunPod volume, not fatal in local dev)"
    free_gib = shutil.disk_usage(p).free / (1024**3)
    return f"exists, {free_gib:.1f} GiB free"


_CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("python", _check_python),
    ("torch", _check_torch),
    ("faiss", _check_faiss),
    ("sqlalchemy", _check_sqlalchemy),
    ("pillow", _check_pillow),
    ("persistent_root /workspace/bikematch", lambda: _check_disk_path("/workspace/bikematch")),
    ("working_root /var/lib/bikematch", lambda: _check_disk_path("/var/lib/bikematch")),
]


@app.command()
def doctor() -> None:
    """Verify the environment by function, not by import-existence."""
    all_ok = True
    for name, fn in _CHECKS:
        if not _run_check(name, fn):
            all_ok = False

    typer.echo("")
    typer.echo("Not yet implemented (Phase 2+): " + ", ".join(_NOT_YET_IMPLEMENTED))

    if not all_ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
