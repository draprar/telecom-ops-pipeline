# syntax=docker/dockerfile:1
# Stage 1: build - install dependencies into a user-local prefix, keep build
# tooling and pip caches out of the final image.
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: runtime - slim image, non-root user, only what's needed to run.
FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system appuser \
    && useradd --system --gid appuser --home-dir /home/appuser --create-home appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh
COPY . .

RUN chown -R appuser:appuser /app

# Set HOME explicitly: switching USER does not reset $HOME on its own, and
# Python's expanduser()/site-packages lookup trusts $HOME over /etc/passwd,
# so a stale value here would silently break the --user package install above.
ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "scripts/run_pipeline.py"]