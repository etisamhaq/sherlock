# Sherlock — container image for the webhook server.
FROM python:3.11-slim AS base

# Links the GHCR package to the source repo (shows on the repo sidebar).
LABEL org.opencontainers.image.source="https://github.com/etisamhaq/sherlock"
LABEL org.opencontainers.image.description="AI SRE that root-causes Kubernetes incidents"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

# Run as a non-root user (defense in depth — Sherlock only needs read-only RBAC).
RUN useradd --create-home --uid 10001 sherlock
USER 10001

EXPOSE 8080

# Default: run the webhook server. Override with `sherlock investigate ...` for a one-off.
ENTRYPOINT ["sherlock"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
