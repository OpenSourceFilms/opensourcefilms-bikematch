# bikematch

Private visual matching service that helps owners of stolen bicycles in Greater
Edinburgh discover marketplace advertisements which may show their bicycle.

There is no public website, no public searchable database and no enforcement
component. The system ends at private matching, archiving and notification.

Built by [Open Source Films](https://github.com/OpenSourceFilms), with GPU
development and testing on [RunPod](https://runpod.io) — see Storage model
below for how its Network Volumes shape the architecture.

## Workflows

**Stolen bike** — owner emails photographs → system archives the email and
photographs → searches all historic collected advertisements → continually
checks future advertisements → emails likely matches → owner replies
`YES` / `NO` / `UNSURE`.

**Buyer / shop reverse check** — a shop or prospective buyer emails photographs
→ system compares them against submitted stolen-bike cases → replies with no
significant match / possible match / strong match → the original owner may also
be alerted.

## Storage model

Two roots, and the distinction is load-bearing:

| Root | Nature | Contents |
|---|---|---|
| `/workspace/bikematch` | RunPod Network Volume, **canonical** | `archive/`, `snapshots/`, `models/`, `browser_profiles/`, `benchmark/`, `exports/`, `backups/` |
| `/var/lib/bikematch` | container-local, **disposable cache** | `state.sqlite3`, `faiss/`, `temp/` |

The filesystem archive is the source of truth. The SQLite database and the FAISS
indexes are operational projections that can be destroyed and rebuilt from the
archive without re-running GPU inference — derived features are persisted to the
network volume for exactly that reason.

Active SQLite WAL files must never live on the network volume: RunPod documents
that simultaneous writes from multiple workers can corrupt a Network Volume.

Note that this repository root and the canonical data root are the same
directory. `.gitignore` separates code from data; the data directories are never
committed.

## Environment

The interpreter, the virtualenv and the package caches all live on the
persistent volume, because the container overlay (`/`, ~30 GB) is destroyed on
rebuild:

```
interpreter   /workspace/.pod-persist/uv-python/cpython-3.13.8-linux-x86_64-gnu
virtualenv    /workspace/bikematch/.venv
uv cache      /workspace/.cache/uv
```

Reproduce the environment after a pod rebuild with:

```bash
bash scripts/restore_env.sh
```

`uv.lock` is authoritative. Do not hand-edit pins in `pyproject.toml` without
re-locking and re-running the test suite.

### Version notes

The pins follow the handover specification. Two are deliberately held one
release behind the current PyPI latest, and should only move as a considered
bump with a full test run:

| Package | Pinned | Latest at lock time |
|---|---|---|
| `faiss-cpu` | 1.14.3 | 1.15.0 |
| `playwright` | 1.61.0 | 1.62.0 |

### GPU

The development pod this was built on has **no GPU** — no `/dev/nvidia*`, no
`libcuda`, no driver. `torch` is the standard PyPI build (CUDA-enabled on
linux/x86-64) so the lockfile matches the intended production runtime, but
`torch.cuda.is_available()` is `False` here and GPU acceptance criteria cannot
be verified on this pod. Everything through Phase 5 is CPU work; the Phase 6
retrieval benchmark is the first step that genuinely wants a GPU pod.

## Development

```bash
uv run bikematch doctor      # environment/dependency diagnostics -- the only CLI command implemented so far
uv run pytest                # excludes tests marked `live`
uv run ruff check .
uv run mypy
```

## Status

Early stage. See the phase plan in `docs/HANDOVER.md`. As of this publication,
Phase 1 (repository, locked environment, `ids.py`) is substantially complete;
Phase 2 (canonical evidence archive) and everything after it — the database,
collectors, matching pipeline, email intake — has not been started yet. There
is no running matcher, no collector, and no deployed instance behind this repo
today. It is published early so the design and progress are visible, not as a
claim that the service is operational.

## Further reading

- [`docs/HANDOVER.md`](docs/HANDOVER.md) — the full architecture spec (42 sections).
- [`docs/DATA_HANDLING.md`](docs/DATA_HANDLING.md) — what this project collects and the boundary around it.
- [`docs/SECURITY.md`](docs/SECURITY.md) — how to report a vulnerability.

