# syntax=docker/dockerfile:1.7
# One image for web, worker and migrations. Built in CI, pushed to GHCR,
# pulled by the Droplet. Targets: `dev` (local hot reload) and `runtime`.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG NODE_IMAGE=node:22-bookworm-slim

# --- Frontend build ------------------------------------------------------------
FROM ${NODE_IMAGE} AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build   # writes /src/backend/frontend_dist

# --- OS packages shared by dev and runtime -------------------------------------
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
# PostgreSQL 16 client (pg_dump must match the server's major version) from
# the official PGDG repository, and `age` for encrypting backups.
# `upgrade` pulls in Debian security fixes released after the base image.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-16 age \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app

# --- Python dependencies -------------------------------------------------------
FROM base AS pydeps
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
COPY backend/requirements/base.txt /tmp/base.txt
RUN pip install --require-hashes -r /tmp/base.txt

FROM pydeps AS pydeps-dev
COPY backend/requirements/dev.txt /tmp/dev.txt
RUN pip install --require-hashes -r /tmp/dev.txt

# --- Development image (code is bind-mounted) -----------------------------------
FROM base AS dev
COPY --from=pydeps-dev /venv /venv
ENV PATH=/venv/bin:$PATH DJANGO_SETTINGS_MODULE=config.settings.dev
WORKDIR /app/backend
USER app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- Production image ----------------------------------------------------------
FROM base AS runtime
ARG APP_VERSION=dev
ENV PATH=/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    APP_VERSION=${APP_VERSION}
COPY --from=pydeps /venv /venv
WORKDIR /app/backend
COPY --chown=root:root backend/ ./
COPY --from=frontend --chown=root:root /src/backend/frontend_dist ./frontend_dist
# Deploy scripts travel inside the image so the Droplet always runs the
# version that matches the code being deployed.
COPY --chown=root:root infra/deploy/ /app/deploy/
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
 && python -m compileall -q /app/backend \
 && chmod +x /app/backend/docker-entrypoint.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["web"]
