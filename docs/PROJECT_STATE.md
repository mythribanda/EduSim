# EduSim-Hub: Comprehensive Project State & Technical Discovery

> **Document Type:** System Discovery & Verification Audit  
> **Date:** November 4, 2026  
> **Status:** Current codebase audit against unverified assumptions  
> **Target File:** `docs/PROJECT_STATE.md`  
> **Execution Constraint:** Discovery only — zero runtime changes, installs, or migrations applied.

---

## 1. What This Project Is

**EduSim** (historically referenced in architectural merges as **EduSim-Hub** / **Smart Student Hub**) is an interactive, simulation-driven STEM learning platform engineered to bridge conceptual textbook physics and physical intuition. The platform combines 2D interactive physics sandboxes (powered by Matter.js and Pixi.js), deterministic formula manipulation labs (powered by SymPy), an AI-powered Socratic tutor, and an offline-capable dense vector retrieval-augmented generation (RAG) engine based on NCERT and state-board textbooks.

### Intended Users
1. **Students (Primary):** Learners across primary and secondary grades (Classes 1–10/12) who browse curriculum topics, interact with visual physics simulations, manipulate formula variables in real-time, ask conceptual questions to the Socratic AI tutor, and practice adaptive MCQ quizzes.
2. **Teachers / Educators:** Instructors navigating the same learning materials, simulations, and formula labs to demonstrate concepts during classroom instruction or review student activity.
3. **Administrators:** System operators managing database seeding, user roles, vector indexing, and administrative system endpoints.

### User Flows That Actually Exist in Code
- **Authentication & Onboarding Flow:** Users register via email/password, Google OAuth2 ID token, or mobile OTP, selecting either the `student` or `teacher` role during registration ([`app/src/api/auth.py`](file:///EduSim_API/app/src/api/auth.py#L182-L321)). Users log in, obtain a 30-minute JWT Bearer access token and a 7-day refresh token, and manage active sessions ([`app/src/api/auth.py`](file:///EduSim_API/app/src/api/auth.py#L249-L278)).
- **Curriculum Exploration Flow:**
  - *Legacy V1 Flow:* User navigates Class (1–10) $\rightarrow$ Subject $\rightarrow$ Chapter $\rightarrow$ Topic via [`curriculumService.ts`](file:///EduSim_frontend/src/services/curriculumService.ts) and [`curriculum_router.py`](file:///EduSim_API/app/src/api/curriculum_router.py).
  - *V2 Pipeline Flow:* User accesses digitized book catalog, chapter summaries, and hierarchical curriculum trees via [`curriculum_v2_router.py`](file:///EduSim_API/app/src/api/curriculum_v2_router.py#L129-L265).
- **Interactive Physics Simulation Flow:** User opens pre-configured static simulations (e.g. projectile motion, pendulum, inclined plane, collision, spring-mass in [`app/src/modules/simulations/static/`](file:///EduSim_API/app/src/modules/simulations/static/)) or generates dynamic custom simulation scenes via LLM synthesis ([`simulation_router.py`](file:///EduSim_API/app/src/api/simulation_router.py#L24-L58)), rendered in the 2D Matter.js/Pixi canvas ([`src/sandbox/engine/`](file:///EduSim_frontend/src/sandbox/engine/)).
- **Formula Lab Exploration Flow:** User enters a physics equation (e.g. $F = ma$, $V = IR$), which is parsed and verified via SymPy; interactive variable sliders allow real-time parameter tweaking and frontend evaluation ([`app/src/api/formula.py`](file:///EduSim_API/app/src/api/formula.py#L23-L28), [`app/src/services/formula_service.py`](file:///EduSim_API/app/src/services/formula_service.py)).
- **Socratic AI Tutor Interaction Flow:** User asks conceptual or contextual questions while interacting with a simulation or reading a topic. The system routes the prompt through the unified AI Router to local Ollama (`gemma3:4b`), augmented with dense FAISS textbook context chunks retrieved via semantic similarity search ([`app/src/api/tutor_router.py`](file:///EduSim_API/app/src/api/tutor_router.py#L51-L120), [`app/src/services/ai_router.py`](file:///EduSim_API/app/src/services/ai_router.py#L155-L277)).
- **Adaptive Quiz & Topic Mastery Flow:** User requests practice questions for a topic. The backend checks the cached `questions` table; if insufficient questions exist, Ollama generates the shortfall. When a user submits an answer, the deterministic mastery engine recalculates accuracy and streak metrics, updating the student's mastery score and recommended difficulty ([`app/src/api/questions.py`](file:///EduSim_API/app/src/api/questions.py#L21-L46), [`app/src/services/mastery.py`](file:///EduSim_API/app/src/services/mastery.py#L60-L166)).
- **Non-Existent / Dropped Flows:** No teacher assignment creation, submission grading, classroom management, or school-wide analytics reports exist in code.

---

## 2. Repo Map

### Top-Level Directory Tree

```text
EduSim/
├── .github/                       # GitHub Actions workflows and CI automation
│   └── workflows/ci.yml           # Backend (pyflakes, pytest) & frontend (eslint, tsc) CI
├── docs/                          # Developer guides and system documentation
│   ├── PROJECT_STATE.md           # This discovery document
│   └── TROUBLESHOOTING.md         # Operational debugging reference
├── EduSim_API/                    # FastAPI backend service (Port 8001)
│   ├── alembic/                   # Database migration environment and version scripts
│   │   └── versions/              # 17 versioned migration scripts (schema evolutions)
│   ├── app/                       # Application source code
│   │   └── src/
│   │       ├── api/               # FastAPI route controllers (auth, tutor, rag, sim, etc.)
│   │       ├── config/            # Database engine, settings, model chains, thresholds
│   │       ├── data/              # Static curriculum fixtures (curriculum.json, 11.8k lines)
│   │       ├── middleware/        # Security exception handlers and RBAC dependencies
│   │       ├── models/            # SQLAlchemy declarative models & Pydantic schemas
│   │       ├── modules/           # Domain modules (legacy_rag, sandbox, tutor, synthesis)
│   │       ├── repositories/      # Data access layer repositories
│   │       ├── services/          # Core business logic (ai_router, mastery, questions, etc.)
│   │       └── utils/             # Cryptographic helpers, JWT tokens, password hashing
│   ├── curriculum/                # Legacy TypeScript curriculum mirror (curriculum.ts)
│   ├── curriculum_pipeline/       # Production textbook PDF ingestion, chunking & catalog engine
│   │   ├── adapters/              # Board-specific PDF format adapters (NCERT, SSC)
│   │   ├── config/                # Regex rules, activity keywords, pipeline settings
│   │   ├── output/                # Extracted JSON trees, chunks, inventory CSV, QA reports
│   │   └── schemas/               # JSON and SQL schemas for curriculum validation
│   ├── data/                      # Persistent runtime caches (formula_extraction_cache.json)
│   ├── faiss_index/               # Legacy 384-d FAISS index (index.faiss, metadata.pkl)
│   ├── faiss_index_v2/            # Production unified multi-subject FAISS index (17,789 vectors)
│   ├── scripts/                   # CLI maintenance scripts (create_admin, ingest, etc.)
│   ├── tests/                     # Backend unit, integration, and RAG evaluation tests
│   ├── textbooks/                 # Local PDF textbook repository (ncert books/ & Text Books/)
│   ├── Dockerfile                 # Multi-stage Python 3.11-slim container definition
│   ├── entrypoint.sh              # Container startup script (migrations + uvicorn)
│   ├── main.py                    # FastAPI application initialization and gateway routes
│   └── requirements.txt           # Pinned Python package dependencies
├── EduSim_frontend/               # React 19 + Vite 7 SPA (Port 8080 / Dev 5173)
│   ├── src/                       # Frontend application source
│   │   ├── ai/                    # Web-worker and AI streaming helpers
│   │   ├── components/            # Reusable UI widgets, Radix UI shells, MathJax/KaTeX
│   │   ├── config/                # Frontend runtime API URL configurations
│   │   ├── data/                  # Offline fallback curriculum data (curriculum.ts, 5.9k lines)
│   │   ├── hooks/                 # Custom React hooks (auth, simulation canvas, queries)
│   │   ├── lib/                   # Utility helpers and UI class merge functions
│   │   ├── routes/                # File-based TanStack Router routes (dashboard, tutor, etc.)
│   │   ├── sandbox/               # Matter.js physics engine, canvas controllers, UI overlays
│   │   ├── services/              # HTTP API client services (TutorService, CurriculumService)
│   │   ├── store/                 # Zustand global client state stores (auth, tutor, sim)
│   │   ├── types/                 # TypeScript interfaces and simulation DSL types
│   │   ├── utils/                 # LaTeX display formatters and formula parsers
│   │   ├── main.tsx               # Client entrypoint and DOM hydration
│   │   └── router.tsx             # TanStack Router configuration
│   ├── Dockerfile                 # Production frontend build & static server container
│   ├── package.json               # NPM dependencies and development scripts
│   ├── tsconfig.json              # TypeScript compilation parameters
│   └── vite.config.ts             # Vite build, plugin, and proxy configuration
├── scripts/                       # Root-level audit and RAG benchmarking scripts
├── tests/                         # Root-level static simulation tests and RAG benchmark YAMLs
├── docker-compose.yml             # Orchestration for Postgres, API, Frontend, and optional Ollama
├── README.md                      # High-level architecture documentation
├── .env.example                   # Root environment template for docker-compose
└── .gitignore                     # Repository ignore rules
```

### Entry Points, Startup & Port Configurations

| Service | Directory / Entrypoint | Startup Command | Configured Ports | Notes & Potential Conflicts |
|---|---|---|---|---|
| **EduSim_API** (FastAPI) | [`EduSim_API/main.py`](file:///EduSim_API/main.py) | `uvicorn main:app --host 0.0.0.0 --port 8001` or [`entrypoint.sh`](file:///EduSim_API/entrypoint.sh) | `8001` (Docker: `8001:8001`) | **Verified.** Configured in [`docker-compose.yml:40`](file:///docker-compose.yml#L40) and [`EduSim_API/Dockerfile:27`](file:///EduSim_API/Dockerfile#L27). CORS allows 8080, 5173, 3000. |
| **EduSim_frontend** (React/Vite) | [`EduSim_frontend/src/main.tsx`](file:///EduSim_frontend/src/main.tsx) | `vite dev` (local dev) or containerized HTTP server | Dev: `5173`<br>Prod/Docker: `8080` | **Port Divergence Flag:** Local `npm run dev` serves on `5173`, whereas Docker Compose maps `8080:8080` ([`docker-compose.yml:85`](file:///docker-compose.yml#L85)). Backend CORS explicitly permits both. |
| **PostgreSQL Database** | Official Docker Image `postgres:16-alpine` | Container entrypoint | `5432` (Docker: `5432:5432`) | **Verified.** Configured in [`docker-compose.yml:14`](file:///docker-compose.yml#L14). SQLite fallback (`edusim.db`) used when `DATABASE_URL` is unset. |
| **Ollama Local LLM** | Host process or optional Docker Compose profile `ollama` | `ollama serve` | `11434` (Docker: `11434:11434`) | **Verified.** Backend connects to host via `http://host.docker.internal:11434` or `http://localhost:11434`. |
| **Next.js Teacher Portal** | *(Claimed: Port 3000)* | **None** | **None** | **CONFLICT / DOES NOT EXIST.** There is no Next.js project in the repo. Port 3000 is only an allowed CORS origin string in [`main.py:14`](file:///EduSim_API/main.py#L14). |

---

## 3. Tech Stack, Verified

### Service Manifests & Versions

#### Backend Service (`EduSim_API`)
- **Language / Runtime:** Python 3.11 (Dockerfile uses `python:3.11-slim`, CI runs `3.11` in [`.github/workflows/ci.yml:26`](file:///.github/workflows/ci.yml#L26)).
- **Core Framework:** FastAPI `0.136.1` ([`EduSim_API/requirements.txt:15`](file:///EduSim_API/requirements.txt#L15)), Starlette `1.0.0` ([`requirements.txt:74`](file:///EduSim_API/requirements.txt#L74)), Uvicorn `0.46.0` ([`requirements.txt:88`](file:///EduSim_API/requirements.txt#L88)).
- **Data Validation & Settings:** Pydantic `2.13.3` ([`requirements.txt:50`](file:///EduSim_API/requirements.txt#L50)), Pydantic-Settings `2.14.0` ([`requirements.txt:51`](file:///EduSim_API/requirements.txt#L51)).
- **Database & ORM:** SQLAlchemy `2.0.49` ([`requirements.txt:72`](file:///EduSim_API/requirements.txt#L72)), Alembic `1.15.2` ([`requirements.txt:73`](file:///EduSim_API/requirements.txt#L73)), psycopg2-binary `2.9.12` ([`requirements.txt:59`](file:///EduSim_API/requirements.txt#L59)).
- **Security & Cryptography:** PyJWT `2.13.0` ([`requirements.txt:58`](file:///EduSim_API/requirements.txt#L58)), bcrypt `4.0.1` ([`requirements.txt:13`](file:///EduSim_API/requirements.txt#L13)), passlib `1.7.4` ([`requirements.txt:57`](file:///EduSim_API/requirements.txt#L57)), google-auth `2.49.2` ([`requirements.txt:94`](file:///EduSim_API/requirements.txt#L94)), authlib `1.3.1` ([`requirements.txt:95`](file:///EduSim_API/requirements.txt#L95)).
- **Vector Search & ML:** FAISS-CPU `1.13.2` ([`requirements.txt:14`](file:///EduSim_API/requirements.txt#L14)), sentence-transformers `5.4.1` ([`requirements.txt:69`](file:///EduSim_API/requirements.txt#L69)), transformers `5.8.0` ([`requirements.txt:81`](file:///EduSim_API/requirements.txt#L81)), PyTorch `2.11.0` ([`requirements.txt:79`](file:///EduSim_API/requirements.txt#L79)), NumPy `2.4.4` ([`requirements.txt:46`](file:///EduSim_API/requirements.txt#L46)), SciPy `1.17.1` ([`requirements.txt:68`](file:///EduSim_API/requirements.txt#L68)), Scikit-Learn `1.8.0` ([`requirements.txt:67`](file:///EduSim_API/requirements.txt#L67)).
- **PDF Extraction & Math:** PyMuPDF (fitz) `1.27.2.3` ([`requirements.txt:55`](file:///EduSim_API/requirements.txt#L55)), PyPDF `6.10.2` ([`requirements.txt:56`](file:///EduSim_API/requirements.txt#L56)), SymPy `1.14.0` ([`requirements.txt:75`](file:///EduSim_API/requirements.txt#L75)).
- **HTTP Client:** HTTPX `0.28.1` ([`requirements.txt:24`](file:///EduSim_API/requirements.txt#L24)).

#### Frontend Service (`EduSim_frontend`)
- **Language / Runtime:** TypeScript `5.8.3` ([`EduSim_frontend/package.json:101`](file:///EduSim_frontend/package.json#L101)), Node.js 22 (CI runs `22` in [`.github/workflows/ci.yml:64`](file:///.github/workflows/ci.yml#L64)).
- **UI Framework:** React `19.2.0` ([`package.json:63`](file:///EduSim_frontend/package.json#L63)), React-DOM `19.2.0` ([`package.json:65`](file:///EduSim_frontend/package.json#L65)). *(Note: `README.md` claims React 18, but package manifest specifies React 19).*
- **Build Tool / Bundler:** Vite `7.3.1` ([`package.json:103`](file:///EduSim_frontend/package.json#L103)). *(Note: `README.md` claims Vite 6, but package manifest specifies Vite 7).*
- **Routing & State:** `@tanstack/react-router` `1.168.0` ([`package.json:48`](file:///EduSim_frontend/package.json#L48)), `@tanstack/react-start` `1.167.14` ([`package.json:49`](file:///EduSim_frontend/package.json#L49)), `@tanstack/react-query` `5.83.0` ([`package.json:47`](file:///EduSim_frontend/package.json#L47)), Zustand `5.0.13` ([`package.json:83`](file:///EduSim_frontend/package.json#L83)).
- **Physics Simulation Engines:** Matter.js `0.19.0` ([`package.json:61`](file:///EduSim_frontend/package.json#L61)), Pixi.js `8.18.1` ([`package.json:62`](file:///EduSim_frontend/package.json#L62)).
- **Styling & Components:** TailwindCSS `4.2.1` ([`package.json:78`](file:///EduSim_frontend/package.json#L78)), Radix UI primitives ([`package.json:20-45`](file:///EduSim_frontend/package.json#L20-L45)), Framer Motion `12.38.0` ([`package.json:56`](file:///EduSim_frontend/package.json#L56)), Lucide React `0.575.0` ([`package.json:59`](file:///EduSim_frontend/package.json#L59)), Recharts `2.15.4` ([`package.json:72`](file:///EduSim_frontend/package.json#L72)).
- **Math & Markdown:** KaTeX `0.16.46` ([`package.json:58`](file:///EduSim_frontend/package.json#L58)), react-katex `3.1.0` ([`package.json:68`](file:///EduSim_frontend/package.json#L68)), mathjs `11.9.0` ([`package.json:60`](file:///EduSim_frontend/package.json#L60)), react-markdown `10.1.0` ([`package.json:69`](file:///EduSim_frontend/package.json#L69)).

---

### Database: Engine, Migrations, Schema & RLS

- **Engine:** PostgreSQL 16 (in Docker Compose: `postgres:16-alpine`), with transparent local SQLite fallback (`sqlite:///./edusim.db`) supported via [`app/src/config/database.py:20-34`](file:///EduSim_API/app/src/config/database.py#L20-L34).
- **Migration Framework:** Alembic (17 migration scripts in [`alembic/versions/`](file:///EduSim_API/alembic/versions/)).
- **Schema & Tables (Verified from Models & DB Inspection):**
  1. `users`: UUID primary key, `name`, `email` (unique index), `password_hash`, `role` (`student`, `teacher`, `admin`), `mobile_number`, verification flags, OTP code/expiry/lock counters, timestamps ([`app/src/models/user.py`](file:///EduSim_API/app/src/models/user.py#L9-L46)).
  2. `books` (V2 Curriculum): UUID pk, `code` (unique, e.g. `aejm1`), `title`, `board`, `class_num`, `subject`, `language`, `total_pages`, `ocr_page_count`, `text_quality`, `sha256`, `is_active` ([`app/src/models/curriculum_pipeline_models.py:21-45`](file:///EduSim_API/app/src/models/curriculum_pipeline_models.py#L21-L45)).
  3. `curriculum_nodes` (V2 Curriculum): UUID pk, `book_id` (FK to `books.id` on delete CASCADE), `chapter_number`, `level` (`chapter`, `topic`, `subtopic`, `activity`), `parent_id` (self-referencing FK), `order_index`, `title`, `page_start`, `page_end`, `identity_key` (unique per book) ([`app/src/models/curriculum_pipeline_models.py:48-80`](file:///EduSim_API/app/src/models/curriculum_pipeline_models.py#L48-L80)).
  4. `curriculum_classes` (V1 Legacy): Integer pk, `name`, `description`, `display_order` ([`app/src/models/persistence.py:31-38`](file:///EduSim_API/app/src/models/persistence.py#L31-L38)).
  5. `subjects` (V1 Legacy): UUID pk, `class_id` (FK to `curriculum_classes.id`), `code`, `name`, `display_order` ([`app/src/models/persistence.py:40-54`](file:///EduSim_API/app/src/models/persistence.py#L40-L54)).
  6. `chapters` (V1 Legacy): UUID pk, `subject_id` (FK to `subjects.id`), `name`, `display_order` ([`app/src/models/persistence.py:56-68`](file:///EduSim_API/app/src/models/persistence.py#L56-L68)).
  7. `topics` (V1 Legacy): UUID pk, `chapter_id` (FK to `chapters.id`), `name`, `has_simulation`, `simulation_route` ([`app/src/models/persistence.py:70-84`](file:///EduSim_API/app/src/models/persistence.py#L70-L84)).
  8. `student_profiles`: `user_id` (FK to `users.id` pk), `skill_level`, `mastered_topics` (JSON), `misconceptions` (JSON) ([`app/src/models/persistence.py:160-168`](file:///EduSim_API/app/src/models/persistence.py#L160-L168)).
  9. `student_topic_mastery`: UUID pk, `student_id` (FK to `users.id`), `topic_id`, `mastery_score` (Float), `correct_streak`, `total_attempts`, `total_correct`, `last_attempted_at`. Unique on `(student_id, topic_id)` ([`app/src/models/school.py:23-46`](file:///EduSim_API/app/src/models/school.py#L23-L46)).
  10. `questions`: UUID pk, `topic`, `difficulty`, `class_level`, `question`, `options` (JSON), `correct`, `explanation`, `created_at` ([`app/src/models/school.py:48-68`](file:///EduSim_API/app/src/models/school.py#L48-L68)).
  11. `session_events`: UUID pk, `student_id` (FK to `users.id`), `module_id`, `event_type`, `payload` (JSON), `created_at` ([`app/src/models/persistence.py:170-186`](file:///EduSim_API/app/src/models/persistence.py#L170-L186)).
  12. `chat_history`: UUID pk, `user_id` (FK to `users.id`), `session_id`, `session_type`, `role`, `topic`, `content` ([`app/src/models/persistence.py:86-98`](file:///EduSim_API/app/src/models/persistence.py#L86-L98)).
  13. `formula_history`: UUID pk, `user_id` (FK to `users.id`), `session_id`, `formula_id`, `input_json`, `output_json` ([`app/src/models/persistence.py:100-111`](file:///EduSim_API/app/src/models/persistence.py#L100-L111)).
  14. `simulation_history`: UUID pk, `user_id` (FK to `users.id`), `simulation_id`, `prompt`, `dsl_json`, `runtime_json` ([`app/src/models/persistence.py:113-129`](file:///EduSim_API/app/src/models/persistence.py#L113-L129)).
  15. `user_settings`: UUID pk, `user_id` (FK to `users.id`), `setting_key`, `setting_value` (JSON) ([`app/src/models/persistence.py:131-142`](file:///EduSim_API/app/src/models/persistence.py#L131-L142)).
  16. `user_sessions`: UUID pk, `user_id` (FK to `users.id`), `session_key`, `device_info`, `expires_at`, `is_active` ([`app/src/models/persistence.py:144-158`](file:///EduSim_API/app/src/models/persistence.py#L144-L158)).
  17. `alembic_version`: Standard Alembic tracking table.
- **Dropped Tables:** `classes`, `teacher_class_subjects`, `student_enrollments`, `assignments`, and `submissions` were explicitly removed from the database in migration [`j0d1e2f3a4b5_remove_classes_assignments_analytics.py`](file:///EduSim_API/alembic/versions/j0d1e2f3a4b5_remove_classes_assignments_analytics.py#L26-L35).
- **RLS / Access Rules:** **None in SQL.** PostgreSQL Row-Level Security is NOT enabled on any table. All access control and IDOR protections are implemented strictly in Python application middleware ([`require_admin`](file:///EduSim_API/app/src/middleware/rbac.py#L21) and [`require_self_or_admin`](file:///EduSim_API/app/src/middleware/rbac.py#L31)).

---

### Auth: Login, JWT, OAuth & RBAC

- **Password Login:** [`POST /api/auth/login`](file:///EduSim_API/app/src/api/auth.py#L249). Plaintext passwords are verified against bcrypt hashes stored in `users.password_hash` using `bcrypt.checkpw` ([`app/src/utils/auth.py:37`](file:///EduSim_API/app/src/utils/auth.py#L37)). Optional role parameter validates user role match. Successful authentication yields a 30-minute access token and a 7-day refresh token.
- **JWT Implementation:** Built with `PyJWT` (`HS256`). Cryptographic key is read from `JWT_SECRET` / `JWT_SECRET_KEY` and strictly verified at startup to be $\ge 32$ characters ([`app/src/utils/auth.py:8-19`](file:///EduSim_API/app/src/utils/auth.py#L8-L19)).
- **Google OAuth:** [`POST /api/auth/google`](file:///EduSim_API/app/src/api/auth.py#L321). Frontend loads Google GSI client library ([`__root.tsx:125`](file:///EduSim_frontend/src/routes/__root.tsx#L125)) and transmits the Google ID token. The backend validates it against Google's token verification service via `google.oauth2.id_token.verify_oauth2_token` ([`app/src/api/auth.py:335-339`](file:///EduSim_API/app/src/api/auth.py#L335-L339)). If the account exists, the session starts; if not, an account is provisioned with a synthetic password sentinel (`OAUTH_GOOGLE_SENTINEL_<uuid>`).
- **Mobile OTP:** [`POST /api/auth/send-otp`](file:///EduSim_API/app/src/api/auth.py#L570) and [`POST /api/auth/verify-otp`](file:///EduSim_API/app/src/api/auth.py#L616). Generates a random 6-digit OTP code valid for 5 minutes. Implements rate limiting and locking after 5 failed attempts for 15 minutes ([`app/src/api/auth.py:643-655`](file:///EduSim_API/app/src/api/auth.py#L643-L655)). *(Note: SMS transmission is currently stubbed to logger output; no external SMS gateway is configured).*
- **RBAC Architecture:**
  - Role values: `student`, `teacher`, `admin`, constrained by database check constraint `ck_users_role` ([`app/src/models/user.py:44`](file:///EduSim_API/app/src/models/user.py#L44)). Role `educator` was renamed to `teacher` in migration [`i9c0d1e2f3a4_standardize_user_roles.py`](file:///EduSim_API/alembic/versions/i9c0d1e2f3a4_standardize_user_roles.py#L22).
  - Backend enforcement: [`app/src/middleware/rbac.py`](file:///EduSim_API/app/src/middleware/rbac.py) only defines `require_admin` and `require_self_or_admin`. There are **no teacher-specific permission gates** in the backend. Both students and teachers are treated as regular authenticated users.
  - Frontend enforcement: The UI inspects `user?.role` and renders a badge (`STUDENT` or `TEACHER`) on the dashboard ([`dashboard.tsx:160`](file:///EduSim_frontend/src/routes/dashboard.tsx#L160)), but all routes, pages, and interactive labs are identical for both roles.

---

### AI Layer: Models, Providers, Prompts, RAG & Caching

- **Hybrid AI Inference Router:** Centralized in [`app/src/services/ai_router.py`](file:///EduSim_API/app/src/services/ai_router.py).
  - *Primary Provider (Edge/Local):* Local Ollama server running `gemma3:4b` at `http://localhost:11434` (or `http://host.docker.internal:11434` in Docker). Features a cheap cached preflight check (`GET /api/tags`, 2s timeout, 30s TTL) ([`ai_router.py:63-121`](file:///EduSim_API/app/src/services/ai_router.py#L63-L121)) before sending requests with a 180s read timeout (`OLLAMA_TIMEOUT`).
  - *Fallback Provider (Cloud):* OpenRouter API via HTTPX (`https://openrouter.ai/api/v1/chat/completions`) ([`app/src/config/models.py:8`](file:///EduSim_API/app/src/config/models.py#L8)). Triggered only when `USE_CLOUD_AI=true` or when Ollama fails and `ALLOW_CLOUD_FALLBACK=true` ([`ai_router.py:281-326`](file:///EduSim_API/app/src/services/ai_router.py#L281-L326)).
  - *Configured Models:*
    - Local: `gemma3:4b` (`OLLAMA_MODEL`).
    - Cloud Default: `google/gemini-2.5-flash` in [`app/src/config/models.py:9`](file:///EduSim_API/app/src/config/models.py#L9) with fallback to `google/gemini-2.5-flash-lite`. In `.env.example`, `OPENROUTER_MODEL=anthropic/claude-3.5-sonnet` is documented.
- **Prompts:**
  - Socratic Tutor: `ULTIMATE_TUTOR_PROMPT` ([`app/src/modules/legacy_rag/prompt_templates/ultimate_tutor_prompt.txt`](file:///EduSim_API/app/src/modules/legacy_rag/prompt_templates/ultimate_tutor_prompt.txt)), `NEW_RENDERING_SYSTEM` and `TUTOR_SYSTEM_PROMPT` ([`app/src/modules/legacy_rag/generator.py:27-100`](file:///EduSim_API/app/src/modules/legacy_rag/generator.py#L27-L100)).
  - Simulation Synthesis: Structured JSON DSL prompts in [`app/src/modules/simulation_synthesis/prompt_builder.py`](file:///EduSim_API/app/src/modules/simulation_synthesis/prompt_builder.py).
  - Question Generation: Structured MCQ prompt in [`app/src/services/question_service.py:152-160`](file:///EduSim_API/app/src/services/question_service.py#L152-L160).
- **RAG Pipeline (Embeddings, Vector Store, Chunking):**
  - *Source Material:* Real PDF textbooks stored in `EduSim_API/textbooks/` (NCERT chapter PDFs in `ncert books/` and State Board whole-book PDFs in `Text Books/`).
  - *Ingestion & Chunking:* [`EduSim_API/curriculum_pipeline/`](file:///EduSim_API/curriculum_pipeline/) extracts clean text using PyMuPDF (`fitz`), maps custom Adobe symbol/PUA font encodings, suppresses repetitive headers/footers, and produces structured `.jsonl` chunks with metadata (`book_code`, `class`, `subject`, `chapter_number`, `page_start`, `page_end`).
  - *Embeddings:* SentenceTransformers model `all-MiniLM-L6-v2` generating 384-dimensional dense vectors ([`app/src/modules/legacy_rag/embedder.py:19-35`](file:///EduSim_API/app/src/modules/legacy_rag/embedder.py#L19-L35)). Supports `query: ` / `passage: ` instruction prefixes when using E5 models.
  - *Vector Store:* FAISS dense index (`IndexFlatIP` with L2-normalized cosine distance). Active production index is located in [`EduSim_API/faiss_index_v2/`](file:///EduSim_API/faiss_index_v2/):
    - `index.faiss`: 27.3 MB binary index file.
    - `metadata.json`: 40.6 MB metadata store containing 17,789 text chunks.
    - `index_manifest.json`: specifies `model_name: all-MiniLM-L6-v2`, `dimension: 384`, `vector_count: 17789`.
  - *Vector Loader & Search:* Global singleton [`VectorStoreManager`](file:///EduSim_API/app/src/modules/legacy_rag/vector_loader.py#L35) preloads FAISS on FastAPI startup. [`CurriculumRetriever`](file:///EduSim_API/app/src/modules/legacy_rag/retriever.py) executes semantic queries with subject and class metadata filters.
- **Caching Mechanisms:**
  - *Question Generation Cache:* Managed by [`QuestionService`](file:///EduSim_API/app/src/services/question_service.py#L78-L139). Queries are checked against the `questions` table by `(topic, difficulty, class_level)`. If sufficient MCQs exist in the database, they are returned immediately at zero AI inference cost. Ollama is only invoked to generate the shortfall.
  - *Formula Extraction Cache:* Stored on disk in [`EduSim_API/data/formula_extraction_cache.json`](file:///EduSim_API/data/formula_extraction_cache.json) to avoid repeated SymPy and LLM formula parsing.
  - *Ollama Preflight Tags Cache:* In-memory TTL cache (30 seconds) in [`ai_router.py:27-35`](file:///EduSim_API/app/src/services/ai_router.py#L27-L35).

---

### Config: Environment Variables Inventory

*(Never printing secret values, only variable names, locations, and descriptions)*

| Environment Variable Name | Service | File Where Used | Purpose & Description |
|---|---|---|---|
| `DATABASE_URL` | Backend | [`app/src/config/database.py:16`](file:///EduSim_API/app/src/config/database.py#L16), [`settings.py:36`](file:///EduSim_API/app/src/config/settings.py#L36) | Connection string for PostgreSQL or SQLite. |
| `DB_SSLMODE` | Backend | [`app/src/config/database.py:28`](file:///EduSim_API/app/src/config/database.py#L28) | Optional SSL mode for PostgreSQL (`require`, `disable`). |
| `JWT_SECRET` | Backend | [`app/src/utils/auth.py:8`](file:///EduSim_API/app/src/utils/auth.py#L8), [`settings.py:26`](file:///EduSim_API/app/src/config/settings.py#L26) | Primary HMAC-SHA256 signing key for JWT tokens ($\ge 32$ chars). |
| `JWT_SECRET_KEY` | Backend | [`app/src/utils/auth.py:8`](file:///EduSim_API/app/src/utils/auth.py#L8), [`settings.py:26`](file:///EduSim_API/app/src/config/settings.py#L26) | Fallback alias for `JWT_SECRET`. |
| `SECRET_KEY` | Backend | [`tests/conftest.py`](file:///EduSim_API/tests/test_ai_router_modes.py) | Testing fallback alias for JWT secret. |
| `GOOGLE_CLIENT_ID` | Backend | [`app/src/api/auth.py:30`](file:///EduSim_API/app/src/api/auth.py#L30) | Google OAuth 2.0 Client ID for server-side ID token verification. |
| `GOOGLE_CLIENT_SECRET` | Backend | [`.env.example`](file:///EduSim_API/.env.example#L92) | Google OAuth client secret (defined in env templates). |
| `SUPABASE_URL` | Backend | [`app/src/config/settings.py:12`](file:///EduSim_API/app/src/config/settings.py#L12), [`app/src/api/auth.py:325`](file:///EduSim_API/app/src/api/auth.py#L325) | Supabase project URL validation parameter. |
| `SUPABASE_KEY` | Backend | [`.env.example`](file:///EduSim_API/.env.example) | Supabase API key (defined in env template). |
| `ALLOWED_ORIGINS` | Backend | [`main.py:19`](file:///EduSim_API/main.py#L19) | Comma-separated list of allowed CORS origins. |
| `FRONTEND_URL` | Backend | [`main.py:23`](file:///EduSim_API/main.py#L23) | Allowed frontend origin URL appended to CORS whitelist. |
| `ADDITIONAL_CORS_ORIGINS` | Backend | [`main.py:23`](file:///EduSim_API/main.py#L23) | Secondary comma-separated CORS origins. |
| `USE_CLOUD_AI` | Backend | [`app/src/services/ai_router.py:182`](file:///EduSim_API/app/src/services/ai_router.py#L182) | Flag forcing AI router to bypass Ollama and use OpenRouter directly. |
| `ALLOW_CLOUD_FALLBACK` | Backend | [`app/src/services/ai_router.py:187`](file:///EduSim_API/app/src/services/ai_router.py#L187) | Permits automatic fallback to OpenRouter when Ollama fails. |
| `ENABLE_OPENROUTER_FALLBACK` | Backend | [`app/src/services/ai_router.py:191`](file:///EduSim_API/app/src/services/ai_router.py#L191) | Legacy alias for `ALLOW_CLOUD_FALLBACK`. |
| `OLLAMA_BASE_URL` | Backend | [`app/src/services/ai_router.py:10`](file:///EduSim_API/app/src/services/ai_router.py#L10) | HTTP endpoint for local Ollama server (`http://localhost:11434`). |
| `OLLAMA_MODEL` | Backend | [`app/src/services/ai_router.py:13`](file:///EduSim_API/app/src/services/ai_router.py#L13) | Model tag executed by Ollama (default: `gemma3:4b`). |
| `OLLAMA_TIMEOUT` | Backend | [`app/src/services/ai_router.py:16`](file:///EduSim_API/app/src/services/ai_router.py#L16) | Ollama HTTP read timeout in seconds (default: `180`). |
| `OLLAMA_KEEP_ALIVE` | Backend | [`app/src/services/ai_router.py:20`](file:///EduSim_API/app/src/services/ai_router.py#L20) | Duration to keep Ollama model loaded in VRAM/RAM (default: `30m`). |
| `OLLAMA_NUM_CTX` | Backend | [`app/src/services/ai_router.py:23`](file:///EduSim_API/app/src/services/ai_router.py#L23) | Context window size for Ollama in tokens (default: `4096`). |
| `OLLAMA_MAX_CHUNKS` | Backend | [`.env.example`](file:///EduSim_API/.env.example#L63) | Maximum RAG chunks included in prompt context. |
| `OLLAMA_MAX_CONTEXT_TOKENS` | Backend | [`.env.example`](file:///EduSim_API/.env.example#L64) | Maximum token count allocated to context. |
| `OLLAMA_TIMEOUT_SECONDS` | Backend | [`.env.example`](file:///EduSim_API/.env.example#L66) | Script generation timeout used by batch topic generator. |
| `OPENROUTER_API_KEY` | Backend | [`app/src/config/models.py:14`](file:///EduSim_API/app/src/config/models.py#L14), [`ai_router.py:186`](file:///EduSim_API/app/src/services/ai_router.py#L186) | API key for OpenRouter cloud LLMs. |
| `OPENROUTER_MODEL` | Backend | [`app/src/config/models.py:15`](file:///EduSim_API/app/src/config/models.py#L15) | Primary OpenRouter cloud model identifier. |
| `OPENROUTER_FALLBACK_MODELS` | Backend | [`app/src/config/models.py:29`](file:///EduSim_API/app/src/config/models.py#L29) | Comma-separated list of fallback cloud models. |
| `EMBEDDING_MODEL` | Backend | [`app/src/modules/legacy_rag/embedder.py:24`](file:///EduSim_API/app/src/modules/legacy_rag/embedder.py#L24), [`rebuild_index.py:25`](file:///EduSim_API/rebuild_index.py#L25) | SentenceTransformer model name (default: `all-MiniLM-L6-v2`). |
| `FAISS_INDEX_V2_DIR` | Backend | [`app/src/modules/legacy_rag/vector_loader.py:29`](file:///EduSim_API/app/src/modules/legacy_rag/vector_loader.py#L29) | Directory path for production unified FAISS index (`faiss_index_v2`). |
| `TEXTBOOKS_DIR` | Backend | [`curriculum_pipeline/pipeline_config.py:32`](file:///EduSim_API/curriculum_pipeline/pipeline_config.py#L32) | Directory path for textbook PDFs (`EduSim_API/textbooks`). |
| `POSTGRES_USER` | Compose | [`docker-compose.yml:10`](file:///docker-compose.yml#L10) | PostgreSQL username in Docker Compose. |
| `POSTGRES_PASSWORD` | Compose | [`docker-compose.yml:11`](file:///docker-compose.yml#L11) | PostgreSQL password in Docker Compose. |
| `POSTGRES_DB` | Compose | [`docker-compose.yml:12`](file:///docker-compose.yml#L12) | PostgreSQL database name in Docker Compose. |
| `VITE_API_URL` | Frontend | [`src/config/api.ts:7`](file:///EduSim_frontend/src/config/api.ts#L7) | Base backend API URL consumed by frontend client. |
| `VITE_GOOGLE_CLIENT_ID` | Frontend | [`src/routes/__root.tsx`](file:///EduSim_frontend/src/routes/__root.tsx) | Google OAuth Web Client ID for Google Sign-In button. |

---

## 4. What Is Built: Feature Status Matrix

| Feature | Status | Evidence (File Paths) | Notes |
|---|---|---|---|
| **User Authentication (Password + JWT)** | **Working** | [`EduSim_API/app/src/api/auth.py#L182-L318`](file:///EduSim_API/app/src/api/auth.py#L182-L318), [`EduSim_API/app/src/utils/auth.py`](file:///EduSim_API/app/src/utils/auth.py), [`EduSim_API/tests/test_auth_roles.py`](file:///EduSim_API/tests/test_auth_roles.py) | Full registration, login, JWT issuance, token refresh, password hashing with bcrypt, session tracking. Fully covered by unit tests. |
| **Google OAuth2 Login** | **Working** (Online) | [`EduSim_API/app/src/api/auth.py#L321-L436`](file:///EduSim_API/app/src/api/auth.py#L321-L436), [`EduSim_frontend/src/routes/__root.tsx#L125`](file:///EduSim_frontend/src/routes/__root.tsx#L125) | Validates ID token against Google's public keys. Requires active internet connection to contact Google APIs. |
| **Email Verification & Password Reset** | **Partial / Stubbed** | [`EduSim_API/app/src/api/auth.py#L238,L529,L740`](file:///EduSim_API/app/src/api/auth.py#L238) | Tokens are generated, hashed, and stored in the database. Email transmission is marked `TODO` and logs to terminal; no SMTP or email gateway configured. |
| **Mobile Number OTP Verification** | **Partial / Stubbed** | [`EduSim_API/app/src/api/auth.py#L570-L705`](file:///EduSim_API/app/src/api/auth.py#L570-L705) | Rate-limiting, lockouts, and OTP matching are implemented and working. SMS sending is stubbed to console output; no SMS gateway configured. |
| **Role-Based Access Control (RBAC)** | **Working** (Limited Scope) | [`EduSim_API/app/src/middleware/rbac.py`](file:///EduSim_API/app/src/middleware/rbac.py), [`EduSim_API/app/src/models/user.py#L44`](file:///EduSim_API/app/src/models/user.py#L44), [`EduSim_API/alembic/versions/i9c0d1e2f3a4_standardize_user_roles.py`](file:///EduSim_API/alembic/versions/i9c0d1e2f3a4_standardize_user_roles.py) | Roles `student`, `teacher`, `admin` enforced via DB check constraint. `require_admin` and `require_self_or_admin` dependencies protect routes. No teacher-specific restrictions exist. |
| **Curriculum V1 (Legacy Navigation)** | **Working** | [`EduSim_API/app/src/api/curriculum_router.py`](file:///EduSim_API/app/src/api/curriculum_router.py), [`EduSim_API/app/src/data/curriculum.json`](file:///EduSim_API/app/src/data/curriculum.json), [`EduSim_frontend/src/services/curriculumService.ts`](file:///EduSim_frontend/src/services/curriculumService.ts) | Serves Classes 1–10 from SQLite/Postgres tables (`curriculum_classes`, `subjects`, `chapters`, `topics`) seeded from `curriculum.json`. |
| **Curriculum V2 (Textbook Pipeline)** | **Working** | [`EduSim_API/app/src/api/curriculum_v2_router.py`](file:///EduSim_API/app/src/api/curriculum_v2_router.py), [`EduSim_API/curriculum_pipeline/`](file:///EduSim_API/curriculum_pipeline/), [`EduSim_API/tests/test_curriculum_v2_router.py`](file:///EduSim_API/tests/test_curriculum_v2_router.py) | Full textbook ingestion engine for 129 books across Classes 1–12; 46 extracted, 25 loaded into DB (2,493 nodes), with REST endpoints for books, chapter summaries, and hierarchical trees. |
| **Topic Mastery Engine** | **Working** | [`EduSim_API/app/src/services/mastery.py`](file:///EduSim_API/app/src/services/mastery.py), [`EduSim_API/app/src/models/school.py#L23-L46`](file:///EduSim_API/app/src/models/school.py#L23-L46), [`EduSim_API/tests/test_mastery.py`](file:///EduSim_API/tests/test_mastery.py) | 100% deterministic pure Python math. Computes mastery score ($0-100$) using accuracy (60%) and consecutive correct streaks (40%). Recommends difficulty (easy/medium/hard). Unit tests pass. |
| **Cached Question Generation** | **Working** | [`EduSim_API/app/src/services/question_service.py`](file:///EduSim_API/app/src/services/question_service.py), [`EduSim_API/app/src/api/questions.py`](file:///EduSim_API/app/src/api/questions.py), [`EduSim_API/app/src/models/school.py#L48-L68`](file:///EduSim_API/app/src/models/school.py#L48-L68) | Queries `questions` table first. If cached count $\ge$ requested count, returns immediately with 0 AI cost. Calls Ollama only for shortfall, parses JSON output, and persists new questions. |
| **Socratic AI Tutor** | **Working** | [`EduSim_API/app/src/api/tutor_router.py`](file:///EduSim_API/app/src/api/tutor_router.py), [`EduSim_API/app/src/services/ai_router.py`](file:///EduSim_API/app/src/services/ai_router.py), [`EduSim_API/app/src/modules/tutor/service.py`](file:///EduSim_API/app/src/modules/tutor/service.py), [`EduSim_frontend/src/routes/tutor.tsx`](file:///EduSim_frontend/src/routes/tutor.tsx) | Multimodal Socratic chat with streaming SSE, query intent parsing, subject detection, conversation history persistence, and MathJax/KaTeX LaTeX rendering. |
| **Dense Vector RAG Engine** | **Working** | [`EduSim_API/app/src/modules/legacy_rag/vector_loader.py`](file:///EduSim_API/app/src/modules/legacy_rag/vector_loader.py), [`EduSim_API/app/src/modules/legacy_rag/retriever.py`](file:///EduSim_API/app/src/modules/legacy_rag/retriever.py), [`EduSim_API/faiss_index_v2/`](file:///EduSim_API/faiss_index_v2/) | 17,789 vector FAISS index preloaded on backend boot. Performs sub-50ms dense semantic search with class and subject filtering. Gracefully degrades if index is absent. |
| **Physics Simulation Sandbox (Matter.js)** | **Working** | [`EduSim_frontend/src/sandbox/`](file:///EduSim_frontend/src/sandbox/), [`EduSim_frontend/src/routes/sandbox.$simulationId.tsx`](file:///EduSim_frontend/src/routes/sandbox.$simulationId.tsx), [`EduSim_API/app/src/modules/sandbox/`](file:///EduSim_API/app/src/modules/sandbox/) | 2D rigid-body kinematics engine with interactive drag-and-drop objects, gravity wells, collisions, spring constraints, pause/play, time scaling, and snapshot saving. |
| **Formula Lab Engine** | **Working** | [`EduSim_API/app/src/services/formula_service.py`](file:///EduSim_API/app/src/services/formula_service.py), [`EduSim_API/app/src/api/formula.py`](file:///EduSim_API/app/src/api/formula.py), [`EduSim_frontend/src/components/formula-lab/FormulaLabPage.tsx`](file:///EduSim_frontend/src/components/formula-lab/FormulaLabPage.tsx) | SymPy AST expression evaluator, parameter sliders with dynamic ranges, persistent extraction cache, and LaTeX formula visualization. |
| **Student Portal Pages** | **Working** | [`EduSim_frontend/src/routes/`](file:///EduSim_frontend/src/routes/) (`index`, `dashboard`, `subjects`, `chapters`, `topics`, `simulation`, `formula-lab`, `tutor`, `profile`, `settings`) | Complete set of responsive pages with active learning widgets, streak tracking, recent session resumption, and topic cards. |
| **Teacher Portal Pages** | **Not Started / Does Not Exist** | None | There is no separate teacher portal. Users with role `teacher` use the student portal with a `TEACHER` badge. |
| **Assignments & Submissions** | **Broken / Dropped** | [`EduSim_API/alembic/versions/j0d1e2f3a4b5_remove_classes_assignments_analytics.py`](file:///EduSim_API/alembic/versions/j0d1e2f3a4b5_remove_classes_assignments_analytics.py) | Database tables `assignments` and `submissions` were dropped in Alembic revision `j0d1e2f3a4b5`. No code remains to assign or grade homework. |
| **Reports & Analytics System** | **Not Started** | None | No student performance reporting, class gradebooks, or administrator analytics dashboards exist in code. Only raw session events are logged to `session_events`. |
| **Admin Seeding & User Management** | **Working** | [`EduSim_API/scripts/create_admin.py`](file:///EduSim_API/scripts/create_admin.py), [`EduSim_API/app/src/api/curriculum_router.py#L130-L203`](file:///EduSim_API/app/src/api/curriculum_router.py#L130-L203) | CLI script to seed/update admin credentials; API endpoint `POST /api/seed` (requires admin JWT) to seed curriculum tables. |

---

## 5. External Dependencies and Network Usage

The following is an exhaustive audit of all runtime calls made to the external internet. Every item in this list must be eliminated or localized to achieve 100% offline LAN operation.

| Category | External Destination | Initiating Source File & Line | Runtime Trigger & Behavior | Offline Risk / Remediation Needed |
|---|---|---|---|---|
| **Google Sign-In Script** | `https://accounts.google.com/gsi/client` | [`EduSim_frontend/src/routes/__root.tsx:125`](file:///EduSim_frontend/src/routes/__root.tsx#L125) | Loaded in `<head>` on every page render. | **Blocks offline rendering.** Fails when browser lacks internet. Must be removed or made conditionally loaded only when online. |
| **Google OAuth Verification** | `https://www.googleapis.com/oauth2/v3/certs` | [`EduSim_API/app/src/api/auth.py:335-339`](file:///EduSim_API/app/src/api/auth.py#L335-L339) | Invoked when `POST /api/auth/google` is called to verify ID token signature. | **Fails offline.** `google_requests.Request()` throws a network exception. Must be disabled or bypassed in offline mode. |
| **Cloud LLM API** | `https://openrouter.ai/api/v1/chat/completions` | [`EduSim_API/app/src/config/models.py:8`](file:///EduSim_API/app/src/config/models.py#L8), [`EduSim_API/app/src/modules/legacy_rag/generator.py:361`](file:///EduSim_API/app/src/modules/legacy_rag/generator.py#L361) | Invoked if `USE_CLOUD_AI=true` or when Ollama fails and `ALLOW_CLOUD_FALLBACK=true`. | **Fails offline.** Throws `httpx.ConnectError`. Must ensure `USE_CLOUD_AI=false` and `ALLOW_CLOUD_FALLBACK=false` on LAN. |
| **Embedding Model Downloads** | `https://huggingface.co/*` | [`EduSim_API/app/src/modules/legacy_rag/embedder.py:27`](file:///EduSim_API/app/src/modules/legacy_rag/embedder.py#L27), [`EduSim_API/curriculum_pipeline/indexer.py:84`](file:///EduSim_API/curriculum_pipeline/indexer.py#L84) | Invoked on startup when `SentenceTransformer("all-MiniLM-L6-v2")` initializes if model weights are not pre-cached in local HuggingFace cache. | **Blocks server boot.** If model cache directory is empty, startup hangs/crashes. Must pre-bundle model weights in Docker image or local directory. |
| **External YouTube Link** | `https://www.youtube.com/results?search_query=...` | [`EduSim_API/app/src/api/curriculum_router.py:93`](file:///EduSim_API/app/src/api/curriculum_router.py#L93) | Returned in JSON search results under `/api/search` as recommended videos. | Minor UI issue: links will fail to open in offline client browsers. |
| **Supabase Hosted DB** | `*.supabase.co:5432` / `*.pooler.supabase.com:6543` | [`EduSim_API/app/src/config/database.py:30-44`](file:///EduSim_API/app/src/config/database.py#L30-L44) | Invoked on every DB operation if `DATABASE_URL` is configured to point to a cloud Supabase instance. | **Fails offline.** Server cannot connect to DB. Must point `DATABASE_URL` to local Postgres container or SQLite. |
| **Web Fonts & CDN Styles** | *None* | [`EduSim_frontend/src/styles.css:1-5`](file:///EduSim_frontend/src/styles.css#L1-L5) | KaTeX stylesheet (`katex/dist/katex.min.css`) and Tailwind are bundled locally via NPM. | **No risk.** Already bundled locally. |
| **Client Analytics** | *None* | Checked across frontend codebase | No Google Analytics, PostHog, Mixpanel, or Sentry scripts found. | **No risk.** Clean. |

---

## 6. Data and Content

### Curriculum & Subject Content Locations
1. **Curriculum V2 Pipeline (Primary Source of Truth):**
   - **Catalog:** [`EduSim_API/curriculum_pipeline/output/catalog/books_catalog.csv`](file:///EduSim_API/curriculum_pipeline/output/catalog/books_catalog.csv) defines 129 NCERT and State Board (SSC) textbooks across Classes 1–12.
   - **Structured Book Trees:** [`EduSim_API/curriculum_pipeline/output/curriculum/books/`](file:///EduSim_API/curriculum_pipeline/output/curriculum/books/) contains 130 validated book JSON definitions conforming to [`book_curriculum.schema.json`](file:///EduSim_API/curriculum_pipeline/schemas/book_curriculum.schema.json).
   - **Textbook Chunks:** [`EduSim_API/curriculum_pipeline/output/chunks/*.jsonl`](file:///EduSim_API/curriculum_pipeline/output/chunks/) contains extracted, denoised, and tokenized chapter chunks with full metadata.
   - **Database Tables:** Tables `books` and `curriculum_nodes` in `edusim.db` / Postgres contain 25 active books and 2,493 hierarchical nodes ([`curriculum_pipeline_models.py`](file:///EduSim_API/app/src/models/curriculum_pipeline_models.py)).
2. **Curriculum V1 JSON Fixtures (Legacy Source of Truth):**
   - **Backend File:** [`EduSim_API/app/src/data/curriculum.json`](file:///EduSim_API/app/src/data/curriculum.json) (11,880 lines). Defines Classes 1 to 10 with subjects (Mathematics, EVS, General Science, Physics, Biology), chapter names, and topic names.
   - **Frontend Mirror:** [`EduSim_frontend/src/data/curriculum.ts`](file:///EduSim_frontend/src/data/curriculum.ts) (5,983 lines). Contains Classes 1 to 12 (including Classes 11–12 with Science, Commerce, and Arts streams). Maintained strictly as an offline fallback when backend API is unreachable.
3. **Physical PDF Textbooks:**
   - [`EduSim_API/textbooks/ncert books/`](file:///EduSim_API/textbooks/ncert%20books/): Chapter PDFs for NCERT books (e.g. `aejm.pdf`, `iemh.pdf`, `leph.pdf`).
   - [`EduSim_API/textbooks/Text Books/`](file:///EduSim_API/textbooks/Text%20Books/): Full-volume PDFs for State Board (SSC 2025–26) books (e.g. `X Physics EM 2025-26.pdf`, `VI General Science EM 2025-26.pdf`).
4. **Seed Scripts & Fixtures:**
   - **Curriculum Seeding:** Endpoint `POST /api/seed` in [`curriculum_router.py:130`](file:///EduSim_API/app/src/api/curriculum_router.py#L130) accepts a JSON payload of classes, subjects, chapters, and topics, executing upserts into `curriculum_classes`, `subjects`, `chapters`, and `topics`.
   - **Admin User Seeding:** [`EduSim_API/scripts/create_admin.py`](file:///EduSim_API/scripts/create_admin.py) creates an administrative account in `users` with hashed bcrypt password.
   - **Topic Content Generation:** [`EduSim_API/scripts/generate_topic_content.py`](file:///EduSim_API/scripts/generate_topic_content.py) reads topic definitions from [`sample_topics.json`](file:///EduSim_API/scripts/sample_topics.json) and uses Ollama to pre-generate 3-stage topic payloads (tutor script, formula lab, and simulation config).

---

## 7. Quality and Risks

### Test Coverage & CI Validation
- **Backend Test Suite:** 15 test files in [`EduSim_API/tests/`](file:///EduSim_API/tests/):
  - `test_ai_router_modes.py`: verifies Ollama preflight, timeout handling, and fallback logic.
  - `test_auth_roles.py`: tests user registration, login, role assignment, and JWT expiration.
  - `test_mastery.py`: verifies the deterministic 0–100 mastery score algorithm and difficulty bands.
  - `test_curriculum_v2_router.py`: validates book and tree REST endpoints.
  - `test_rag_grounding.py`, `test_rag_chapter_filter.py`, `test_rag_auth.py`: validates dense FAISS retrieval and metadata filtering.
  - `test_learning_loop.py`: integration test for question generation and submission.
  - `curriculum_pipeline/`: unit tests for extractor, validator, and loader.
- **Root RAG Evaluation:** [`tests/rag_eval/run_eval.py`](file:///tests/rag_eval/run_eval.py) tests grounding accuracy against YAML benchmarks (`questions.yaml`, `questions_hindi.yaml`, `questions_eval_v3.yaml`).
- **Frontend Test Suite:** Only a single unit test exists: [`EduSim_frontend/src/services/TutorService.test.ts`](file:///EduSim_frontend/src/services/TutorService.test.ts). There are **no component tests, widget tests, or integration tests** for the UI, state stores, or Matter.js simulation canvas.
- **CI Pipeline:** [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml) executes:
  - Backend: `pyflakes` on all source dirs + `pytest -q` against temporary SQLite database.
  - Frontend: `npm run lint` (`eslint .`) + `npx tsc --noEmit` (TypeScript typecheck).

### Known Bugs, Dead Code & Duplicated Logic
1. **Dual Curriculum Systems (V1 vs V2 Split):**
   - The repository contains two parallel, un-unified curriculum systems:
     - **V1:** `curriculum_classes`, `subjects`, `chapters`, `topics` populated from `curriculum.json` and consumed by [`students_router.py`](file:///EduSim_API/app/src/api/students_router.py#L67), [`tutor.py`](file:///EduSim_API/app/src/services/tutor.py), and frontend routes.
     - **V2:** `books` and `curriculum_nodes` populated by `curriculum_pipeline` from textbook PDFs and exposed via `/api/books/*`.
   - Result: Topic mastery, student profiles, and the student dashboard reference legacy V1 topic strings, while the vector store and textbook chunks reference V2 book codes.
2. **Duplicated Tutor Implementations:**
   - [`EduSim_API/app/src/services/tutor.py`](file:///EduSim_API/app/src/services/tutor.py) (403 lines) implements Socratic tutoring and mastery score integration.
   - [`EduSim_API/app/src/modules/tutor/service.py`](file:///EduSim_API/app/src/modules/tutor/service.py) (1,770 lines) implements intent classification, RAG retrieval, and simulation explanations.
   - Both are imported in [`tutor_router.py`](file:///EduSim_API/app/src/api/tutor_router.py#L14,L41) to service different endpoints (`/ask` vs `/analyze`).
3. **Dead Code / Stubbed Endpoints:**
   - [`app/src/services/chapter_service.py`](file:///EduSim_API/app/src/services/chapter_service.py): 6-line file where `match_chapter` simply returns the input argument without matching.
   - [`app/src/api/curriculum_router.py:93`](file:///EduSim_API/app/src/api/curriculum_router.py#L93): hardcodes YouTube search query URLs.
   - Removed Smart Student Hub remnants: Migration `j0d1e2f3a4b5` dropped classes, assignments, and enrollments, leaving dead references in comments and TODO notes.
4. **TODO / FIXME Items:**
   - [`auth.py:238,529,608,740`](file:///EduSim_API/app/src/api/auth.py#L238): Email and SMS dispatch are completely un-implemented.
   - [`persistence.py:28`](file:///EduSim_API/app/src/models/persistence.py#L28): `# TODO: [Curriculum V2 Migration] Legacy curriculum models... The source of truth has moved to books and curriculum_nodes`.
   - [`students_router.py:67`](file:///EduSim_API/app/src/api/students_router.py#L67): `# TODO: [Curriculum V2 Migration] Migrate topic resolution & progression to CurriculumNode/Book`.
   - [`tutor.py:101`](file:///EduSim_API/app/src/services/tutor.py#L101): `# TODO: Integrate RAG retrieval into Socratic explanation`.

### Security Concerns
- **Missing Authorization Gates on Learning Endpoints:** Endpoints like `/api/questions/generate`, `/api/formula/extract`, `/api/simulations/generate`, and `/api/tutor/analyze` do not enforce role checking. Any registered user or anonymous caller can trigger LLM inference requests.
- **Google OAuth Dependency in Offline Deployment:** If network fails, Google OAuth authentication is completely non-functional.
- **Unsafe Model Downloads:** If `SentenceTransformer` is initialized on an un-cached environment without pre-downloaded weights, it attempts outbound HTTPS calls to `huggingface.co`.

---

## 8. Requested Changes (Owner Specification)

*(Recorded verbatim; impact analysis and conflicts documented without evaluating feasibility)*

### Change A: Total Offline Operation (Single School LAN Server)
> **Requirement (Verbatim):** "The project must work totally offline (no internet at runtime). It will run on a single school LAN server (FastAPI + database + Ollama), with browsers connecting over the local network."

- **Affected Files & Modules:**
  - `EduSim_frontend/src/routes/__root.tsx` (line 125: external Google GSI script).
  - `EduSim_API/app/src/api/auth.py` (lines 321–356: Google OAuth token validation via Google APIs).
  - `EduSim_API/app/src/services/ai_router.py` (lines 182–198, 279–326: OpenRouter cloud fallback).
  - `EduSim_API/app/src/config/models.py` (lines 8–16: OpenRouter URL and models).
  - `EduSim_API/app/src/modules/legacy_rag/embedder.py` (line 27: SentenceTransformer weights loading).
  - `docker-compose.yml` (network host configurations, environment flags, Ollama container setup).
  - `EduSim_frontend/src/config/api.ts` (API base URL must bind to LAN IP/hostname instead of hardcoded `localhost`).
- **Current Conflicts:**
  - `__root.tsx` loads `https://accounts.google.com/gsi/client`, causing script load errors in offline browsers.
  - `auth.py` invokes `id_token.verify_oauth2_token()` which fetches certs from `googleapis.com`.
  - SentenceTransformer downloads model files from Hugging Face if not pre-baked into container or volume.
  - `VITE_API_URL` defaults to `http://localhost:8001`. On a LAN server, client browsers accessing `http://<lan-server-ip>:8080` will attempt to connect to `localhost:8001` (their own local machine) instead of the LAN server.
- **Open Questions:**
  - Should Google OAuth be completely hidden/disabled in the frontend when running in offline LAN mode?
  - Should the LAN server package Ollama inside Docker Compose or run as a native host daemon on the school server?
  - How will client browsers resolve the backend address (DNS hostname, mDNS, or static LAN IP)?

---

### Change B: NCERT Curriculum Classes 1–10 (2026–27 Content Pack)
> **Requirement (Verbatim):** "Integrate the NCERT curriculum, classes 1-10, 2026-27, as a structured, versioned content pack (topics/subtopics per class and subject) driving mastery tracking and question generation."

- **Affected Files & Modules:**
  - `EduSim_API/app/src/models/persistence.py` (legacy `curriculum_classes`, `subjects`, `chapters`, `topics`).
  - `EduSim_API/app/src/models/curriculum_pipeline_models.py` (`books`, `curriculum_nodes`).
  - `EduSim_API/curriculum_pipeline/` (adapters, chunker, indexer, loader).
  - `EduSim_API/app/src/services/mastery.py` (topic ID references and progression keys).
  - `EduSim_API/app/src/services/question_service.py` (topic caching and prompt formatting).
  - `EduSim_API/app/src/api/students_router.py` (`resolve_topic_name`, `TOPIC_PROGRESSIONS`).
  - `EduSim_frontend/src/data/curriculum.ts` and `EduSim_API/app/src/data/curriculum.json`.
- **Current Conflicts:**
  - Dual curriculum representation: `curriculum.json` (V1) defines classes 1–10 with static topic names, whereas `curriculum_pipeline` (V2) defines 129 books including Classes 11–12 and State Board books.
  - `StudentTopicMastery` uses loose string `topic_id`s that resolve against legacy V1 `topics.name` rather than versioned V2 `curriculum_nodes.identity_key`.
  - Question generation prompt expects physics topics; Classes 1–5 topics are foundational Math and EVS.
  - The current 2025–26 SSC textbooks and pre-2026 NCERT textbooks must be reconciled or upgraded to the 2026–27 edition.
- **Open Questions:**
  - Will 2026–27 NCERT textbooks be provided as official chapter PDFs, or as a pre-compiled JSON/YAML content pack?
  - Should legacy V1 curriculum tables (`curriculum_classes`, `subjects`, `chapters`, `topics`) be completely deprecated in favor of `books` and `curriculum_nodes`?
  - Should subjects beyond physics (Math, EVS, Biology, Chemistry) support question generation and simulations, or will simulations remain focused on physics/kinematics?

---

### Change C: [OWNER TO ADD MORE CHANGES HERE]
- *(Reserved for owner specifications).*

---

## 9. Open Questions for the Owner

1. **Teacher Portal Scope:** The original context assumed a Next.js 14 teacher portal on port 3000, but no such service exists in the codebase (the teacher role is a badge within the unified React SPA). Do you want to build a dedicated teacher dashboard (e.g. class progress, student mastery overviews) within the existing React/Vite SPA, or keep the single unified learner interface?
2. **Assignments & Homework:** Were assignments and student submissions intentionally removed (as indicated by migration `j0d1e2f3a4b5`), or is there a plan to re-introduce assignment creation and grading for offline LAN schools?
3. **Authentication Strategy for LAN Deployment:** In an offline environment without Google OAuth or external email/SMS verification, should user accounts be:
   - Self-registered with simple username/password?
   - Pre-provisioned in bulk by an administrator via CSV/seed script?
   - Guest/session-based without mandatory passwords?
4. **Hardware Specifications of Target School Server:**
   - What CPU, RAM, and GPU hardware will be available on the school LAN server?
   - Will the server have an NVIDIA GPU to run `gemma3:4b` at acceptable tokens/sec for simultaneous classroom student queries, or will Ollama run in CPU-only inference mode?
5. **Curriculum Unification Strategy:** Do you want to eliminate the legacy `curriculum.json` / `curriculum_classes` schema entirely and migrate all navigation, mastery tracking, and question generation to the versioned `books` / `curriculum_nodes` pipeline?
6. **Simulation Coverage for Primary Grades:** Current simulations focus heavily on secondary physics (mechanics, orbits, gravity, optics). How should Classes 1–5 (Math and EVS) be represented in the simulation and formula lab interfaces?
