#!/bin/sh
set -e

# Seed FAISS V2 index into volume if volume is empty
TARGET_INDEX_DIR="${FAISS_INDEX_V2_DIR:-/app/faiss_index_v2}"
mkdir -p "$TARGET_INDEX_DIR"
if [ ! -f "$TARGET_INDEX_DIR/index.faiss" ] || [ ! -f "$TARGET_INDEX_DIR/metadata.json" ]; then
    echo "[EduSim] Target FAISS index at $TARGET_INDEX_DIR is missing or empty. Seeding from image..."
    if [ -d "/app/faiss_index_v2_seed" ] && [ -f "/app/faiss_index_v2_seed/index.faiss" ]; then
        cp -r /app/faiss_index_v2_seed/* "$TARGET_INDEX_DIR/"
        echo "[EduSim] Successfully seeded FAISS V2 index from /app/faiss_index_v2_seed into $TARGET_INDEX_DIR."
    elif [ -d "/app/faiss_index_v2" ] && [ -f "/app/faiss_index_v2/index.faiss" ]; then
        cp -r /app/faiss_index_v2/* "$TARGET_INDEX_DIR/"
        echo "[EduSim] Successfully seeded FAISS V2 index into $TARGET_INDEX_DIR."
    else
        echo "[EduSim] WARNING: No seed FAISS V2 index found to copy into $TARGET_INDEX_DIR."
    fi
fi

# Run database migrations
echo "[EduSim] Running database migrations (alembic upgrade head)..."
alembic upgrade head

# Start FastAPI server
echo "[EduSim] Starting Uvicorn server on port 8001..."
exec uvicorn main:app --host 0.0.0.0 --port 8001
