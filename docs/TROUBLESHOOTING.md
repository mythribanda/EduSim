# EduSim Troubleshooting Guide

## Tutor shows "Failed to fetch"

When the AI Tutor in the frontend displays `Failed to fetch` upon submitting a question, the browser's `fetch()` call to `POST /api/tutor/analyze` was unable to complete a network connection with the backend. Follow these four diagnostic checks to locate and resolve the issue.

---

### Check 1: Backend Startup, Configuration, and Lifespan Validation

The backend startup sequence validates configuration in `lifespan` before opening port 8001. If validation or initialization fails, the process exits or hangs before requests can be received.

1. **Required Environment Variables**:
   Ensure `EduSim_API/.env` exists and specifies:
   - `DATABASE_URL`: Must be defined (e.g., `sqlite:///./edusim.db` or a PostgreSQL connection string like `postgresql://postgres:password@localhost:5432/edusim`). If missing, `validate_config()` in `app/src/config/settings.py` raises `RuntimeError("DATABASE_URL environment variable is missing.")`.
   - `JWT_SECRET` (or `JWT_SECRET_KEY`): Must be set and at least 32 characters long. If missing or shorter than 32 characters, `validate_jwt_secret()` raises `RuntimeError("JWT_SECRET must be at least 32 characters long.")`.
   - `USE_CLOUD_AI`: Set to `true` to use OpenRouter directly, or `false` to attempt local Ollama (`http://localhost:11434`) first with automatic fallback to OpenRouter.

2. **Database Migrations (Alembic)**:
   In Docker (`entrypoint.sh`), `alembic upgrade head` is executed with `set -e` before Uvicorn starts. If a migration fails (such as revision `a7c9e2f4b610` encountering a pre-existing `student_profiles` table in SQLite with `OperationalError: table student_profiles already exists`), the container will crash immediately. Ensure migration scripts check table existence idempotently:
   ```bash
   cd EduSim_API
   .\venv\Scripts\alembic.exe upgrade head
   ```

3. **SentenceTransformer & PyTorch Lifespan Initialization**:
   During `vector_store.load_all()`, the backend loads the embedding model `sentence-transformers/all-MiniLM-L6-v2`. If:
   - Torch or Faiss dependencies fail to import (e.g. missing C++ redistributable or virtual environment mismatch), the server raises an `ImportError`.
   - The Hugging Face Hub is unreachable on first run (and weights are not yet cached in `~/.cache/huggingface`), the startup process may hang or time out.

---

### Check 2: Backend Process and Health Verification

Confirm the backend is actively listening on port 8001 and able to query the database and execute inference:

1. **Root Health Check**:
   ```bash
   curl -i http://localhost:8001/
   ```
   Expected response:
   ```json
   HTTP/1.1 200 OK
   {"success":true,"message":"EduSim FastAPI Backend Running"}
   ```

2. **Database Health Check**:
   ```bash
   curl -i http://localhost:8001/api/db/health
   ```
   Expected response:
   ```json
   HTTP/1.1 200 OK
   {"success":true,"message":"Connected to SQLite","database_url":"...","version":"..."}
   ```

3. **Direct Tutor Endpoint Test**:
   ```bash
   curl -i -X POST http://localhost:8001/api/tutor/analyze \
     -H "Content-Type: application/json" \
     -d "{\"query\":\"What is Newton's second law?\"}"
   ```
   Expected response: HTTP 200 with structured JSON containing `ai_explanation`, `formulas`, `concepts`, and `simulation_guide`.

---

### Check 3: Frontend Configuration & Build-Time Environment Baking

1. **Verify `EduSim_frontend/.env`**:
   Ensure `EduSim_frontend/.env` exists and defines:
   ```env
   VITE_API_URL=http://localhost:8001
   ```
   - Ensure there is **no trailing `/api`** or trailing slash (e.g., do not use `http://localhost:8001/api`).
   - In `EduSim_frontend/src/config/api.ts`, `API_CONFIG.BASE_URL` sanitizes trailing `/api` and slashes and resolves to `http://localhost:8001`.

2. **Docker Build-Time Environment Notice**:
   In Vite applications, all `VITE_*` variables are replaced at **bundle/build time** (`npm run build`). Setting `VITE_API_URL` as a runtime container environment variable in `docker-compose.yml` does **not** update the compiled browser bundle. If the backend port or host changes, rebuild the frontend image:
   ```bash
   docker compose build --build-arg VITE_API_URL=http://localhost:8001 frontend
   ```

---

### Check 4: CORS and Preflight (OPTIONS) Verification

The browser executes an `OPTIONS` preflight request before sending the actual `POST` request to `/api/tutor/analyze` because custom headers (`Content-Type`, `Authorization`, `X-Request-ID`) are sent. If CORS headers are missing or mismatched, the browser blocks the response and reports `TypeError: Failed to fetch`.

1. **Test CORS Preflight**:
   ```bash
   curl -i -X OPTIONS http://localhost:8001/api/tutor/analyze \
     -H "Origin: http://localhost:8080" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type,authorization,x-request-id"
   ```

2. **Required Preflight Headers**:
   Verify the response contains:
   ```http
   HTTP/1.1 200 OK
   access-control-allow-origin: http://localhost:8080
   access-control-allow-credentials: true
   access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
   access-control-allow-headers: content-type,authorization,x-request-id
   ```
   If `access-control-allow-origin` is missing, verify that `ALLOWED_ORIGINS` in `EduSim_API/.env` includes `http://localhost:8080`.
