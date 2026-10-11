# =============================================================================
# EduSim_API Dockerfile
# Base: python:3.12-slim, non-root user, CPU-only torch, port 8001, healthcheck
# =============================================================================
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8001

WORKDIR /app

# Install system dependencies (curl for healthcheck, build dependencies for potential C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first to avoid downloading multi-gigabyte CUDA wheels
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install remaining dependencies
COPY requirements.txt .
# Filter out torch from requirements.txt to preserve the CPU-only installation
RUN grep -v '^torch==' requirements.txt > requirements-no-torch.txt && \
    pip install --no-cache-dir -r requirements-no-torch.txt && \
    rm requirements-no-torch.txt

# Pre-download SentenceTransformers model so startup does not download from HuggingFace
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Create non-root user and group
RUN groupadd -r edusim && useradd -r -g edusim -u 1000 -d /app edusim

# Copy application source code
COPY . /app

# Ensure directories exist for FAISS indices and textures/data with proper ownership
RUN mkdir -p /app/faiss_index /data/textbooks && \
    chown -R edusim:edusim /app /data/textbooks && \
    chmod +x /app/entrypoint.sh

# Switch to non-root user
USER edusim

EXPOSE 8001

# Healthcheck targeting /api/db/health
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -f http://localhost:8001/api/db/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
