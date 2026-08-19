# Production image for bikematch.
#
# The base is the handover-specified PyTorch runtime image. Note that on the
# development pod this project was built on there is no GPU at all; this image
# targets the intended production runtime, not that pod.
FROM pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    # Models and browsers are large and must not be baked into the overlay.
    HF_HOME=/workspace/bikematch/models \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Playwright's bundled Chromium needs these; ffmpeg/libheif serve the image
# pipeline (HEIC arrives from iPhone owners as a matter of course).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git tini \
        libheif1 libde265-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer first so application edits do not invalidate it.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --all-extras

COPY src/ ./src/
COPY config.example.toml ./
RUN uv sync --frozen --all-extras

RUN uv run playwright install --with-deps chromium

ENV PATH="/app/.venv/bin:${PATH}"

# The canonical archive is a mounted RunPod Network Volume; the working root is
# container-local and deliberately disposable.
VOLUME ["/workspace/bikematch"]
RUN mkdir -p /var/lib/bikematch/faiss /var/lib/bikematch/temp

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bikematch", "doctor"]
