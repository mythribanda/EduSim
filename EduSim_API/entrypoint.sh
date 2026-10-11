#!/bin/sh
set -e

# Run database migrations
echo "[EduSim] Running database migrations (alembic upgrade head)..."
alembic upgrade head

# Start FastAPI server
echo "[EduSim] Starting Uvicorn server on port 8001..."
exec uvicorn main:app --host 0.0.0.0 --port 8001
