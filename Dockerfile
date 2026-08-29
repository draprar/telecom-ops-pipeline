# ---- builder ----
# Installs runtime dependencies into an isolated venv. Kept separate from
# the final stage so pip's build/download cache and pip itself never end
# up in the image that actually ships.
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---- runtime ----
FROM python:3.12-slim AS runtime

# Unprivileged user to run the app as - the image should never run as root.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Only the installed packages come across from the builder stage - no pip
# cache, no pip itself, no pyc/build artifacts.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Only what the app actually needs at runtime - not tests/, dags/, sql/,
# docker-compose.yml, README.md, etc. Keeps the image lean and means a
# change to, say, the DAG file doesn't invalidate this image's layers.
#
# alembic.ini + migrations/ are included because this same image doubles
# as the "migrate" service in docker-compose.yml (command overridden to
# `alembic upgrade head` there) - one image, two jobs, instead of
# maintaining a second image just to run migrations.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser migrations/ ./migrations/

USER appuser

CMD ["python", "scripts/run_pipeline.py"]