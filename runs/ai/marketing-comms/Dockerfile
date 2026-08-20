# The marketing-comms service as one container: the prototype shape (API +
# in-process background worker), not the two-tier target in
# docs/architecture-gcp.md. See docs/deploy-cloud-run.md for what that
# difference means operationally and which knobs to set.
#
# Build from the repo root — the uv project (pyproject.toml, uv.lock) lives
# there, not in this directory:
#
#   docker build -f runs/ai/marketing-comms/Dockerfile -t marketing-comms .

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1

# Dependencies first, so editing source does not invalidate this layer.
# --no-dev keeps pytest/jupyter out; the ml group is not default and stays out.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# The service is read in place from runs/, same as in the repo. Templates ride
# along because layout.contract locates templates/ by walking up from src/.
COPY runs/ai/marketing-comms/src runs/ai/marketing-comms/src
COPY runs/ai/marketing-comms/templates runs/ai/marketing-comms/templates

ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run injects PORT (default 8080). Shell form for the expansion; exec so
# uvicorn is PID 1 and receives SIGTERM for a clean drain.
CMD exec uvicorn api:app --app-dir runs/ai/marketing-comms/src --host 0.0.0.0 --port ${PORT:-8080}
