# MITA ChatGPT app — MCP service image (Railway service "mita-mcp").
# Same repository and domain code as the API image, different dependency set
# (requirements-mcp.txt) and entrypoint. Never runs migrations.

FROM python:3.12-slim AS builder
WORKDIR /install
COPY requirements-mcp.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install/deps --no-cache-dir --disable-pip-version-check \
      -r requirements-mcp.txt

FROM python:3.12-slim
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -r mita && useradd -r -g mita -s /bin/false mita
COPY --from=builder /install/deps /usr/local
WORKDIR /app
COPY --chown=mita:mita app ./app
# app.core.logging_config (imported by the reused domain modules) creates
# ./logs and opens file handlers at import time; configure_logging() closes
# them at startup, but the directory must be writable or the import fails.
RUN mkdir -p /app/logs && chown mita:mita /app/logs
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    PORT=8080
USER mita
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/health" || exit 1
CMD ["python", "-m", "app.mcp"]
