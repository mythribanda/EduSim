# EduSim: Intelligent Adaptive STEM Education & Simulation Ecosystem

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Gemma_3-white.svg?logo=ollama&logoColor=black)](https://ollama.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Executive Summary

**EduSim** is an intelligent, interactive STEM education ecosystem engineered to bridge theoretical physics and practical intuition through high-fidelity simulations and pedagogical AI.

The platform unifies:
- **`EduSim_API`**: A high-performance **FastAPI** backend powering the physics simulation runtime, pedagogical AI tutor, FAISS semantic textbook RAG, and formula lab.
- **`EduSim_frontend`**: A single, modern **React 18 + Vite** application using **TanStack Router** and **Zustand**. Users select their role (**Student** or **Teacher**) directly at login/signup. Both roles enjoy complete, unconstrained access to all interactive learning environments, simulations, the AI tutor, formula lab, and sandboxes.

Powered by a hybrid AI router that prioritizes edge inference via local **Ollama (Gemma 3 4B)** with zero API cost before gracefully failing over to cloud LLMs (**OpenRouter**), EduSim features Socratic dialogue scaffolding, deterministic physics formula exploration, and semantic textbook retrieval.

---

## 🏛️ System Architecture

```text
+===================================================================================================+
|                                    SINGLE UNIFIED FRONTEND LAYER                                  |
+===================================================================================================+
|  EduSim_frontend (Port 8080 / Dev 5173)                                                           |
|  - React 18 + Vite SPA with TanStack Router & Zustand State Store                                 |
|  - Unified Experience with Role-Aware Greeting & Navbar Badge ("Student" / "Teacher")            |
|  - Matter.js 2D Physics Canvas Sandbox & Interactive Particle Simulations                         |
|  - Socratic AI Chat Interface with MathJax/KaTeX LaTeX Rendering                                  |
|  - Formula Lab Explorer & Dynamic Parameter Sliders                                               |
+---------------------------------------------------------------------------------------------------+
                                                │
                                                ▼ (RESTful JSON / Bearer JWT)
+===================================================================================================+
|                                   EduSim_API GATEWAY & ENGINE (Port 8001)                         |
+===================================================================================================+
|  SECURITY & ACCESS CONTROL:                                                                       |
|  - JWT Authentication (>=32-byte cryptographic secret) & Google OAuth2                            |
|  - Segmented Roles: "student" and "teacher" (enforced upon registration & verified on login)      |
|  - Strict IDOR Protection & Ownership Validation                                                  |
+---------------------------------------------------------------------------------------------------+
|  CORE APPLICATION MODULES:                                                                        |
|  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌──────────────────────────────────┐  |
|  │ Context-Aware Tutor     │  │ Formula Lab Engine       │  │ Simulation State Controller      │  |
|  │ - Socratic system prompt│  │ - Physics equation tree  │  │ - AST Math Expression Evaluator  │  |
|  │ - Pedagogical guidance  │  │ - Parameter bounds check │  │   (Safe AST No-Eval Whitelist)   │  |
|  │ - FAISS textbook RAG    │  │ - Dynamic calculation    │  │ - Real-time state persistence    │  |
|  └────────────┬────────────┘  └─────────────┬────────────┘  └─────────────────┬────────────────┘  |
+===============│=============================│=================================│===================+
                ▼                             ▼                                 ▼
+===================================================================================================+
|                                    HYBRID AI INFERENCE ROUTER                                     |
+===================================================================================================+
|                                    Is USE_CLOUD_AI=true ?                                         |
|                                       /              \                                            |
|                          (Yes / Bypass)              (No - Default)                               |
|                                     /                  \                                         |
|                                    │             1. Try Local Ollama                              |
|                                    │                (http://localhost:11434 / Gemma 3 4B)         |
|                                    │                [OLLAMA_TIMEOUT (60s) / 0 API Cost]           |
|                                    │                         │                                    |
|                                    │                 (Timeout or Error)                           |
|                                    │                         │                                    |
|                                    ▼                         ▼                                    |
|                         2. Cloud Fallback: OpenRouter Provider API                                |
|                            (Claude 3.5 Sonnet / GPT-4o-Mini via HTTPS)                            |
+===================================================================================================+
                │                                                          │
                ▼                                                          ▼
+==============================================+ +==================================================+
|  DATA STORAGE & PERSISTENCE LAYER            | |  SEMANTIC KNOWLEDGE BASE                         |
+==============================================+ +==================================================+
|  - PostgreSQL 15 / Supabase / SQLite         | |  - FAISS Dense Vector Index                      |
|  - SQLAlchemy 2.0 ORM + Alembic Migrations   | |  - NCERT / High-School Physics Textbook Chunks   |
|  - Clean Schema: Users, Profiles,            | |  - Resilient Graceful Degradation (503 if missing|
|    Persistent Scenes, Formula Registry       | |    without crashing backend startup)             |
+----------------------------------------------+ +--------------------------------------------------+
```

---

## 🛠️ Tech Stack Overview

| Domain | Technology / Library | Purpose & Architectural Justification |
|---|---|---|
| **Backend Framework** | **FastAPI** (Python 3.11+) | Asynchronous, high-throughput REST API with native Pydantic data validation and OpenAPI auto-docs under `/api`. |
| **Database & ORM** | **PostgreSQL 15** / **SQLite** / **SQLAlchemy 2.0** / **Alembic** | Relational schema management with declarative versioned Alembic migrations (`alembic upgrade head`). |
| **Authentication** | **PyJWT** (HMAC-SHA256) / **Google OAuth2** | Stateless Bearer token verification with two primary roles (`student` and `teacher`). |
| **Local LLM Engine** | **Ollama** (`gemma3:4b`) | Edge inference running locally for zero-cost Socratic responses with configurable timeout. |
| **Cloud LLM Gateway** | **OpenRouter API** (`httpx`) | Resilient cloud fallback handling LLM requests if local Ollama reaches timeout or is offline. |
| **Vector Search / RAG** | **FAISS** + Sentence Transformers | Semantic similarity search retrieving textbook passages within strict token budgets. |
| **Unified Web App** | **React 18** + **Vite** + **TanStack Router** + **Zustand** | Single frontend (`EduSim_frontend`) serving both students and teachers with zero route fragmentation. |
| **Physics Simulation** | **Matter.js** + Safe AST Evaluator | 2D rigid-body kinematics engine paired with a sandbox AST expression evaluator preventing RCE vulnerabilities. |

---

## 🌐 Network Ports & Service Map

| Service | Port | URL | Role / Functionality |
|---|:---:|---|---|
| **FastAPI Backend** | `8001` | [http://localhost:8001](http://localhost:8001) | Primary REST API (`/api`), WebSocket endpoints, AI router |
| **Swagger Interactive Docs** | `8001` | [http://localhost:8001/docs](http://localhost:8001/docs) | Interactive OpenAPI testing console |
| **EduSim Frontend** | `8080` (or `5173`) | [http://localhost:8080](http://localhost:8080) | Unified learning hub: simulations, AI tutor, sandbox & formula lab |
| **Local Ollama Server** | `11434` | [http://localhost:11434](http://localhost:11434) | Local LLM inference server (Gemma 3 4B) |
| **PostgreSQL Database** | `5432` | `postgresql://localhost:5432` | Primary relational database storage |

---

## ⚙️ Environment Variables Reference

### 1. Backend Service (`EduSim_API/.env`)

| Variable | Type | Default / Required | Description |
|---|:---:|:---:|---|
| `DATABASE_URL` | String | **Required** | PostgreSQL or SQLite connection string (`postgresql://user:pass@host:5432/dbname` or `sqlite:///./edusim.db`). |
| `DB_SSLMODE` | String | Optional | Set to `require` when using SSL mode for Postgres. |
| `JWT_SECRET` / `JWT_SECRET_KEY` | String | **Required ($\ge 32$ chars)** | Cryptographic key used to sign and verify user authentication tokens. |
| `USE_CLOUD_AI` | Boolean | `false` | When set to `true`, forces the AI Router to bypass local Ollama and directly use OpenRouter. |
| `OLLAMA_BASE_URL` | URL | `http://localhost:11434` | Endpoint where the local Ollama instance is hosted. |
| `OLLAMA_MODEL` | String | `gemma3:4b` | Default local LLM model tag executed by Ollama. |
| `OLLAMA_TIMEOUT` | Number | `60` | Request timeout in seconds for local Ollama before falling back to OpenRouter. |
| `OPENROUTER_API_KEY` | String | Optional (Required if fallback/cloud used) | API key for OpenRouter cloud LLMs. |
| `OPENROUTER_MODEL` | String | `anthropic/claude-3.5-sonnet` | Default OpenRouter fallback model. |
| `OPENROUTER_FALLBACK_MODELS` | String | Optional | Comma-separated list of secondary cloud fallback models. |
| `FAISS_INDEX_DIR` | Path | `<EduSim_API>/faiss_index` | Absolute directory path where FAISS vector index is stored. |
| `TEXTBOOKS_DIR` | Path | `<EduSim_API>/data/physics` | Absolute directory path containing textbook PDFs. |
| `SUPABASE_URL` | URL | Optional | Supabase project URL (if utilizing Supabase Auth / Storage). |
| `GOOGLE_CLIENT_ID` | String | Optional | Google OAuth 2.0 Client ID for Google login. |
| `ALLOWED_ORIGINS` | String | Optional | Comma-separated allowed CORS origins. |
| `FRONTEND_URL` | URL | `http://localhost:8080` | Allowed CORS origin for the EduSim Frontend. |

### 2. Frontend Application (`EduSim_frontend/.env`)

| Variable | Type | Default | Description |
|---|:---:|:---:|---|
| `VITE_API_URL` | URL | `http://localhost:8001` | Backend API gateway base URL (without trailing `/api`). |
| `VITE_GOOGLE_CLIENT_ID` | String | Optional | Google OAuth 2.0 Client ID for frontend Google sign-in. |

---

## 🚀 Complete Setup & Installation Guide

### Prerequisites
- **Python**: Version 3.10 or 3.11+ installed
- **Node.js**: Version 18.0+ or 20.0+ with `npm`
- **PostgreSQL**: Version 14+ (Local service or cloud Supabase) or local **SQLite**
- **Ollama**: (Optional for local AI) [https://ollama.ai](https://ollama.ai)

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/mythribanda/EduSim.git
cd EduSim
```

---

### Step 2: Configure Ollama (Local AI Engine)
1. Download and start the Ollama daemon:
   ```bash
   ollama serve
   ```
2. In a separate terminal, pull the recommended lightweight physics reasoning model:
   ```bash
   ollama run gemma3:4b
   ```
   *(To run without Ollama, refer to the [Running Without Ollama](#-running-without-ollama-cloud-only-mode) section below).*

---

### Step 3: Backend Setup (`EduSim_API`)
1. Navigate to the backend directory and create a Python virtual environment:
   ```bash
   cd EduSim_API
   python -m venv venv
   ```
2. Activate the virtual environment:
   - **Windows (PowerShell/CMD):**
     ```powershell
     .\venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     source venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file:
   ```bash
   cp .env.example .env
   ```
   *Ensure `DATABASE_URL` is set to your database (PostgreSQL or SQLite) and `JWT_SECRET` has at least 32 characters.*
5. Run database migrations:
   ```bash
   alembic upgrade head
   ```
6. Start the FastAPI backend server:
   ```bash
   uvicorn main:app --reload --port 8001 --host 0.0.0.0
   ```
   *Verify backend is live at: [http://localhost:8001/docs](http://localhost:8001/docs)*

---

### Step 4: Frontend Setup (`EduSim_frontend`)
1. In a new terminal window:
   ```bash
   cd EduSim_frontend
   npm install
   ```
2. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *Access the EduSim Application at: [http://localhost:8080](http://localhost:8080)*

---

## ☁️ Running Without Ollama (Cloud-Only Mode)

If you are running on a machine without a local GPU/Ollama setup, you can switch the entire platform to cloud AI inference in seconds:

1. Open your backend environment file (`EduSim_API/.env`).
2. Add or toggle the following flags:
   ```dotenv
   USE_CLOUD_AI=true
   OPENROUTER_API_KEY=sk-or-v1-your-actual-openrouter-api-key-here
   ```
3. Restart the FastAPI backend.

**What happens behind the scenes:**
- The AI router detects `USE_CLOUD_AI=true` and instantly bypasses local HTTP attempts to `http://localhost:11434`.
- All Socratic tutor queries and concept explanations route directly to cloud LLMs via OpenRouter with zero startup delay.

---

## 🔒 Security & Defense-in-Depth Highlights

1. **Zero Unsafe `eval()` Executions:** Replaced arbitrary Python expression evaluation in physics states with a sandboxed, recursive Abstract Syntax Tree (`ast.parse`) mathematical parser whitelist.
2. **Strict Cryptographic JWT Entropy:** System enforces minimum 32-character high-entropy secret keys during startup with automatic termination on placeholder detection.
3. **IDOR Defense on Sandbox & Sessions:** In-memory tracking and database ownership validation on all sandbox runtimes and historical sessions.
4. **Resilient Vector Store Lifecycle:** Startup checks verify FAISS index availability gracefully without crashing the server, returning HTTP 503 if vectors have not yet been built.
5. **Role-Based Segmentation:** Users select their account role (`student` or `teacher`) at signup; login verifies account role matching without role-based route fragmentation.

---

## 📄 License & Attribution

Distributed under the **MIT License**. Created by Mythri Banda as an advanced, adaptive STEM learning ecosystem.
