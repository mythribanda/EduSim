# EduSim - FastAPI Backend Engine

A robust, production-grade FastAPI backend for the **EduSim** interactive physics learning platform. This service powers the AI Physics Tutor, RAG textbook context retrieval, a high-fidelity Formula Lab with persistent caching, and the interactive physics simulation sandbox orchestrator.

## Key Capabilities

*   **AI Physics Tutor (`/api/tutor`)**: Contextual, multi-turn AI chat grounded in local textbook PDFs. Stores student conversation history in PostgreSQL or SQLite.
*   **RAG Search (`/api/rag`)**: Scans textbook PDFs, uses sentence-transformers (`all-MiniLM-L6-v2`) to embed chunks, and FAISS vector indices for semantic search retrieval.
*   **Formula Lab (`/api/formula`)**: Contextual extraction of physics formulas (hybrid LLM & parser) with **persistent disk-based JSON caching** to eliminate LLM token overhead on repeated topic searches or formula parameter retrievals.
*   **Simulation Sandbox Orchestration (`/api/simulations`)**: Synthesizes and generates physics scene payloads dynamically based on conversational outcomes or manual user requests.
*   **Curriculum Database (`/api/curriculum`)**: Supports multi-class, multi-subject curriculum paths with automated table creation and curriculum seeding.
*   **Authentication (`/api/auth`)**: Secure JWT-based student profiles and session tokens.

---

## Directory Architecture

```
EduSim_API/
├── main.py                  - Core FastAPI server entry point (manages lifespan, DB init & FAISS)
├── alembic.ini              - Database migrations configuration
├── requirements.txt         - Python package dependencies
├── data/                    - Directory containing textbook PDFs and persistent formula extraction cache
│   ├── IX Physics EM 2025-26.pdf
│   └── formula_extraction_cache.json
├── scratch/                 - Diagnostic scripts, database query tools & offline playground experiments
├── api/                     - Root routes (formula, questions, rag)
├── services/                - Generic services (formula_service, rag_service, question_service)
├── app/src/                 - Core platform application
│   ├── api/                 - Endpoint controllers (auth, curriculum, tutor, persistence, etc.)
│   ├── config/              - Database config, OpenRouter config, and fallback models
│   ├── models/              - SQLAlchemy models (User, Persistence history, Curriculum structures)
│   ├── rag/                 - Intel-RAG retriever, topic classifiers, and curriculum payload builder
│   ├── modules/             - Core logic blocks (Tutor agent prompts, Sandbox orchestration, Legacy RAG)
│   ├── repositories/        - Database queries and repository layers
│   └── services/            - Business logic layers
```

---

## Installation & Setup

### 1. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Linux/macOS
# or: venv\Scripts\activate on Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create or edit a `.env` file in the root directory:
```env
OPENROUTER_API_KEY=your_openrouter_api_key
DATABASE_URL=postgresql://username:password@localhost:5432/edusim
```
*If `DATABASE_URL` is omitted, the application will default to a local SQLite database (`edusim.db`).*

### 4. Run Database Migrations
Apply database migrations using Alembic to set up or update the schema:
```bash
alembic upgrade head
```

---

## Running the Server

Start the FastAPI application locally using Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

*   **API Documentation**: Visually inspect endpoints at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.
*   **Health Check**: Ping `http://localhost:8000/` or `http://localhost:8000/api/db/health` to verify database connectivity.

---

## Vector Store (RAG Index)

The FAISS vector index (`vectorstore/`) and the SQLite database (`edusim.db`) are **not committed to the repository** — they are runtime artefacts generated from your local data files.

### Why?
* Binary FAISS index files are large and change every time the PDFs or embedding model change, polluting git history.
* `edusim.db` is a local SQLite file; in production a real `DATABASE_URL` (PostgreSQL) is used instead.

### Regenerating the vector store locally

1. Place your textbook PDFs inside the `data/` directory (e.g. `data/IX Physics EM 2025-26.pdf`).
2. Activate your virtual environment, then run:
   ```bash
   python -m app.src.modules.legacy_rag.rebuild_index
   ```
   This loads all PDFs from `data/`, splits them into chunks, embeds them with `all-MiniLM-L6-v2`, and writes the FAISS index to `vectorstore/physics/`.
3. The server (`main.py`) calls `vector_store.load_all()` on startup and will use the freshly generated index automatically.

> **Note:** If no `vectorstore/` directory exists when the server starts, it will attempt to build the index on first startup from whatever PDFs are in `data/`. Running the rebuild script ahead of time is recommended for a faster startup.

---

## Developer Playground & Testing

To execute experiments, tests, or diagnose features without running the web client:
*   Use the **`scratch/`** directory. All testing scripts (e.g. `test_endpoints.py`, `test_tutor.py`, `debug_extract.py`) have been moved there to keep the root source code directory clean.
*   Run scratch utilities using the virtual environment interpreter:
    ```bash
    venv/bin/python scratch/debug_extract.py
    ```

## License
MIT License
