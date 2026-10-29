#!/bin/sh

# Detiene el inicio si falla algún comando.
set -eu

echo "Running database migrations..."

python -m alembic upgrade head

echo "Starting FastAPI..."

exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"