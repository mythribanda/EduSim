import sys
import os
# Configure Python Path to allow loading absolute namespaces (rag, tutor, sandbox)
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

# CORS configuration — allows Vite/TanStack frontend (port 8080 and dev port 5173).
_default_origins = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
_env_origins = os.getenv("ALLOWED_ORIGINS")
ALLOWED_ORIGINS: list[str] = list(_default_origins)
if _env_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in _env_origins.split(",") if o.strip()])
for _url_env in ("FRONTEND_URL", "ADDITIONAL_CORS_ORIGINS"):
    _val = os.getenv(_url_env)
    if _val:
        ALLOWED_ORIGINS.extend([o.strip() for o in _val.split(",") if o.strip()])
ALLOWED_ORIGINS = sorted(list(set(ALLOWED_ORIGINS)))
sys.path.append(os.path.join(root_dir, "app", "src", "modules"))
sys.path.append(os.path.join(root_dir, "app", "src"))

import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.src.api.simulation_router import simulation_router
from app.src.api.rag_router import rag_router
from app.src.api.tutor_router import tutor_router
from app.src.api.persistence_router import persistence_router
from app.src.modules.sandbox.controller import sandbox_router
from app.src.api.scene_router import scene_router
from app.src.api.auth import auth_router
from app.src.api.curriculum_router import router as curriculum_router
from app.src.api.curriculum_v2_router import router as curriculum_v2_router
from app.src.api.students_router import router as students_router

from app.src.api.formula import router as generic_formula_router
from app.src.api.questions import router as generic_questions_router
from app.src.config.database import ping_database

# Configure global logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("EduSim")
logger.info("EduSim Backend Starting Up...")
logger.info("Formula Registry Loaded")
logger.info("Vector Store Loaded")
logger.info("Chapter Index Loaded")
logger.info("Formula APIs Ready")
logger.info("Question APIs Ready")
logger.info("RAG Ready")
logger.info("Server Ready")

from contextlib import asynccontextmanager
from app.src.modules.legacy_rag.vector_loader import vector_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate critical configuration on startup
    from app.src.config.settings import validate_config
    validate_config()

    # Preload FAISS globally
    vector_store.load_all()
    logger.info(
        "[VectorStore] Resolved index dir: %s | Vectors: %d | Subjects: %d",
        vector_store.resolved_index_dir,
        vector_store.vector_count,
        vector_store.subject_count,
    )
    
    # Database schema is managed via Alembic migrations (alembic upgrade head)
    # Note: Curriculum data is managed via books/curriculum_nodes (V2 curriculum pipeline)
        
    yield

class CatchAllExceptionsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
            logger.exception(
                "Unhandled exception on %s %s (request_id=%s): %s",
                request.method,
                request.url.path,
                request_id,
                exc,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error",
                    "request_id": request_id,
                },
            )

app = FastAPI(
    title="EduSim Physics API",
    description="Backend APIs for EduSim simulations",
    version="1.0.0",
    lifespan=lifespan
)

# Catch-all exception middleware — registered BEFORE CORSMiddleware so that
# CORSMiddleware (registered last, outermost) wraps it and attaches CORS headers
# (e.g. Access-Control-Allow-Origin) to 500 error responses.
app.add_middleware(CatchAllExceptionsMiddleware)

# CORS — origins are restricted to the ALLOWED_ORIGINS env var (see top of file).
# allow_credentials=True is safe here because origins are never wildcarded.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Route
@app.get("/")
async def root():
    logger.info("Health check endpoint pinged.")
    return {
        "success": True,
        "message": "EduSim FastAPI Backend Running"
    }


@app.get("/api/db/health")
async def database_health():
    res = ping_database()
    if not res.get("success", False):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=res)
    return res


# DEPRECATED: use POST /api/simulations/generate
@app.post("/api/generate", deprecated=True)
async def generate_simulation_legacy(
    request: dict,
):
    from app.src.modules.simulation_synthesis.controller import AgentGenerateRequest, synthesis_generate_controller
    req = AgentGenerateRequest(**request)
    return await synthesis_generate_controller(req)


# Simulation & Core Learning Routes (all under /api)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(sandbox_router, prefix="/api")
app.include_router(scene_router, prefix="/api")
app.include_router(simulation_router, prefix="/api/simulations")
app.include_router(rag_router, prefix="/api/rag")
app.include_router(tutor_router, prefix="/api/tutor")
app.include_router(generic_formula_router, prefix="/api/formula")
app.include_router(generic_questions_router, prefix="/api/questions")
app.include_router(persistence_router, prefix="/api/persistence")
app.include_router(curriculum_router, prefix="/api")
app.include_router(curriculum_v2_router, prefix="/api")
app.include_router(students_router, prefix="/api")


