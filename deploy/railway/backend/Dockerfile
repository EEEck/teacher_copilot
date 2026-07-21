# Production backend image for Railway beta.
# Build context: repository root (see deploy/railway/README.md).
FROM python:3.12-slim-bookworm

WORKDIR /app

# Non-root runtime; beta SQLite + workspace wikis write only under /data (Railway volume).
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin app

COPY backend/pyproject.toml .
COPY backend/app ./app
# Seed wiki for beta_cli provision (copytree into BETA_DATA_ROOT/workspaces/...).
COPY backend/teacher_wiki ./teacher_wiki

RUN pip install --no-cache-dir -e . \
    && mkdir -p /data/beta_data \
    && chown -R app:app /app /data

ENV WIKI_ROOT=/app/teacher_wiki \
    BETA_DATA_ROOT=/data/beta_data \
    API_HOST=0.0.0.0 \
    API_PORT=8010

EXPOSE 8010

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os, urllib.request; p=os.environ.get('PORT','8010'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health')"

# No --reload: single production process per Railway replica.
# Railway injects PORT; default 8010 matches local Compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}"]
