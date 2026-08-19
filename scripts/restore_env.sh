#!/usr/bin/env bash
# Reproduce the bikematch environment after a RunPod container rebuild.
#
# The container overlay (/) is destroyed on rebuild; only /workspace survives.
# This script rebuilds everything that lives on the overlay by default --
# notably the uv-managed interpreter, which uv would otherwise place under
# /root/.local/share/uv/python (ephemeral).
#
# Safe to re-run: every step is idempotent.
set -o pipefail

REPO_ROOT="/workspace/bikematch"
export UV_PYTHON_INSTALL_DIR="/workspace/.pod-persist/uv-python"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/workspace/.cache/uv/}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/workspace/.cache/pip/}"
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface/}"

echo "==> uv"
if ! command -v uv >/dev/null 2>&1; then
    echo "FATAL: uv is not installed and is not on /workspace." >&2
    echo "Install it, then re-run: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi
uv --version

echo "==> persistent interpreter"
mkdir -p "$UV_PYTHON_INSTALL_DIR"
uv python install 3.13 || exit 1

echo "==> virtualenv + locked dependencies"
cd "$REPO_ROOT" || exit 1
if [ ! -f uv.lock ]; then
    echo "FATAL: uv.lock missing. The lockfile is authoritative; refusing to" >&2
    echo "resolve fresh versions silently." >&2
    exit 1
fi
uv sync --all-extras --frozen || exit 1

echo "==> container-local working root"
# Disposable cache: SQLite WAL must never sit on the network volume.
mkdir -p /var/lib/bikematch/faiss /var/lib/bikematch/temp

echo "==> verifying by function, not by import-existence"
uv run python - <<'PY' || exit 1
import sys, torch, faiss, sqlalchemy, PIL, numpy
# Exercise the libraries rather than merely importing them.
x = torch.nn.functional.normalize(torch.randn(8, 32), dim=1)
assert abs(float((x * x).sum(dim=1).mean()) - 1.0) < 1e-4, "torch maths wrong"
idx = faiss.IndexFlatIP(32)
idx.add(x.numpy())
d, i = idx.search(x.numpy()[:1], 1)
assert i[0][0] == 0, "faiss self-retrieval wrong"
print(f"python      {sys.version.split()[0]}")
print(f"torch       {torch.__version__}  cuda_available={torch.cuda.is_available()}")
print(f"faiss       {faiss.__version__}")
print(f"sqlalchemy  {sqlalchemy.__version__}")
print(f"numpy       {numpy.__version__}")
print("functional checks: OK")
PY

echo "==> playwright browser (Chromium)"
# Bundled browsers land under the overlay unless redirected.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/workspace/.cache/playwright}"
uv run playwright install chromium || echo "WARNING: playwright chromium install failed"

echo
echo "restore_env.sh complete."
echo "PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"
echo "Remember to export UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR in new shells."
