# EduSim AI Tutor & RAG System — Comprehensive Audit Report

**Date:** November 10, 2026  
**Auditor:** Senior AI/ML & RAG Architecture Specialist  
**Project:** EduSim – Multilingual Voice-Interactive Generative AI Platform  
**Target:** AI Tutor, RAG Retrieval Pipeline, AI Model Integration, Backend & Frontend Connectivity  

---

## 1. Executive Summary

A comprehensive architectural and code audit of the **EduSim** repository was conducted. The system is fundamentally well-structured with strong local-first capabilities, a persistent SQLite/PostgreSQL layer, a dense FAISS vector retrieval system indexed across 17,789 curriculum vectors, a deterministic physics simulation engine (Matter.js), and an AI inference router interfacing with Ollama (`gemma3:4b`) and OpenRouter (`gemini-2.5-flash`).

Key findings of this audit include:
1. **RAG Pipeline & Retrieval Accuracy:** Retrieval performance is exceptionally high (Hit@1: **92.0%**, Hit@5: **96.0%**, MRR: **0.9300**) when filtered with metadata (`class_num` + `subject`). However, the AI Tutor endpoint controller (`analyze_tutor_controller`) was **dropping `class_name`**, falling back to unfiltered retrieval where Hit@1 drops to **48.0%**.
2. **Multilingual RAG & Tutor (Telugu & Hindi):** While multilingual book schemas and evaluation benchmarks (`questions_hindi.yaml`) exist, query language detection and multilingual grounding were missing in the tutor service. Hindi and Telugu queries returned poor retrieval scores (Hit@1: 0%) because `all-MiniLM-L6-v2` is an English-centric embedding model and `detect_subject` only matches English tokens.
3. **AI Model Routing:** The dual-provider architecture (Ollama primary with OpenRouter fallback) is well-implemented in `ai_router.py`. Error handling properly flags `LOCAL_LLM_UNAVAILABLE` (HTTP 503) and `BILLING_CREDIT_LIMIT` (HTTP 402), avoiding silent mock responses.
4. **Curriculum Pipeline Test Glitches:** Out of 148 automated backend tests, 141 passed, 5 skipped, and 2 failed due to minor test assertion inconsistencies (`qa_reporter.py` catalog path filtering and `test_curriculum_extractor.py` page start index).
5. **Evaluation Script Path Resolution:** `tests/rag_eval/run_eval.py` failed when invoked from repo root due to an incorrect `sys.path` search looking for `./app` instead of `./EduSim_API/app`.

---

## 2. Component Classification Matrix

| Component | Status | Classification Notes |
|---|---|---|
| **FastAPI Backend Core (`EduSim_API/main.py`)** | **Working** | App boots cleanly, CORS properly configured, routers mounted under `/api`, lifespan preloads FAISS globally. |
| **Database & Persistence (`database.py`, `persistence.py`, `user.py`)** | **Working** | SQLite & PostgreSQL dual-engine support with Alembic migrations. Session history and mastery score persistence active. |
| **Authentication & RBAC (`auth.py`, `rbac.py`)** | **Working** | JWT access/refresh token lifecycle, bcrypt hashing, student/teacher role isolation. |
| **AI Inference Router (`ai_router.py`)** | **Working** | Preflights Ollama (`gemma3:4b`), enforces request timeouts, and triggers OpenRouter fallback only when authorized. |
| **Vector Store Manager (`vector_loader.py`)** | **Working** | Preloads `faiss_index_v2` (17,789 vectors, 384 dimensions), verifies dimension manifest, sub-50ms inverted index search. |
| **Curriculum Retriever (`retriever.py`)** | **Working** | NumPy-based inverted index pre-filtering by class, subject, board, book code, and chapter number. |
| **AI Tutor Controller & Service (`tutor_router.py`, `service.py`)** | **Partially working** | Socratic tutor functional, but drops `class_name` context argument and lacks language detection. |
| **Multilingual Support (Telugu, Hindi, English)** | **Broken / Incomplete** | No runtime language detection, subject classifier is English-only, prompt lacks target-language instruction. |
| **Curriculum Pipeline Ingestion (`curriculum_pipeline/`)** | **Working** | Ingests PDF textbooks, extracts headings, builds hierarchical JSON trees and chunks. |
| **Frontend AI Tutor Integration (`TutorService.ts`, `tutor.tsx`)** | **Working** | Communicates with `/api/tutor/analyze`, handles session history, displays formulas and RAG references. |
| **Docker & Docker Compose (`docker-compose.yml`)** | **Working** | Health checks, internal bridge network `edusim_net`, volume seeding for FAISS v2. |
| **Automated Evaluation Scripts (`run_eval.py`, `compare_embedders.py`)** | **Requires verification** | `run_eval.py` had broken module import path when run from project root. |

---

## 3. Comprehensive File-by-File Audit Table

| File/Module | Existing functionality | Problem identified | Root cause | Recommended fix |
|---|---|---|---|---|
| `EduSim_API/app/src/modules/tutor/controller.py` | `analyze_tutor_controller`: receives `TutorQueryRequest` from frontend | Drops `request.class_name` when invoking `analyze_tutor_query` | `analyze_tutor_query` did not include `class_name` in its signature | Pass `class_name=request.class_name` and forward to `analyze_tutor_query`. |
| `EduSim_API/app/src/modules/tutor/service.py` | `analyze_tutor_query`: classifies query, runs RAG retrieval, invokes LLM | 1. Does not accept `class_name` parameter.<br>2. Does not detect user language.<br>3. Subject classifier is English-only.<br>4. Prompt does not instruct output language. | Parameter omitted in refactoring; multilingual prompt pipeline was not wired up to the tutor module. | Add `class_name` parameter to `analyze_tutor_query`; add lightweight language detection (English/Hindi/Telugu); cross-lingual concept mapping for RAG; instruct LLM to answer in the user's language. |
| `EduSim_API/app/src/modules/tutor/service.py` | `get_rag_components(subject)`: fetches retriever for subject | Only passes `subject` to retriever; does not support `class_num` | Function only took `subject` | Support passing `class_num` and `subject` into retrieval query. |
| `EduSim_API/app/src/services/ai_router.py` | `call_ai`: routes between Ollama and OpenRouter | In offline mode, if Ollama fails and fallback is disabled, returns error cleanly, but does not provide actionable model pull command in error message if model missing | Error string only from preflight check | Enhance preflight error reporting to include exact Ollama command to pull `gemma3:4b`. |
| `EduSim_API/curriculum_pipeline/qa_reporter.py` | `generate_qa_report`: compiles QA reports across extracted books | Fails in tests with custom/mock books directory (`test_qa_reporter_generation`) | Hardcoded check against production `catalog/books_catalog.csv` filters out non-catalog books even in test runs | Only filter against `books_catalog.csv` if `books_dir` is the default books directory, or if book stem matches. |
| `EduSim_API/tests/curriculum_pipeline/test_curriculum_extractor.py` | `test_tree_builder_case_insensitive_sibling_deduplication`: unit test | Test fails with `assert 10 == 19` | Candidate 1 was initialized at page 10 and candidate 2 at page 19; deduplicated topic keeps start page 10, but test asserted 19 | Fix candidate 1 page to 19 (matching subtopic test structure on page 20) or assert correct start page 10. |
| `tests/rag_eval/run_eval.py` | Evaluates RAG retrieval recall and sweeps similarity thresholds | Fails with `ModuleNotFoundError: No module named 'app'` when executed from repo root | Path resolution checks `(p / "app").is_dir()` instead of `(p / "EduSim_API" / "app")` | Update directory search loop to add `EduSim_API` to `sys.path`. |
| `EduSim_API/app/src/modules/legacy_rag/embedder.py` | `get_embeddings()`: wraps `SentenceTransformer` | Emits deprecation warning `FutureWarning: get_sentence_embedding_dimension has been renamed to get_embedding_dimension` | Older method name called on newer `sentence-transformers 5.x` | Use `get_embedding_dimension()` with fallback to `get_sentence_embedding_dimension()`. |
| `EduSim_frontend/src/services/TutorService.ts` | Frontend API client for AI Tutor | Correctly sends `class_name`, `subject`, `chapter`, `topic` | Backend controller was dropping `class_name` | No frontend changes needed; backend controller fix will immediately connect frontend context to RAG. |

---

## 4. Key Metrics & Benchmark Baseline

From our empirical evaluation of the existing index and questions:
- **Index:** `faiss_index_v2` (17,789 vectors, 384 dimensions, `all-MiniLM-L6-v2`)
- **English RAG Retrieval (Filtered):**
  - Hit@1: **92.0%**
  - Hit@3: **92.0%**
  - Hit@5: **96.0%**
  - MRR: **0.9300**
- **English RAG Retrieval (Unfiltered):**
  - Hit@1: **48.0%**
  - Hit@5: **84.0%**
  - MRR: **0.6367**
- **Optimal Similarity Threshold:** `0.50` (False Refusal Rate: **0.0%**, Out-of-Syllabus Refusal: **90.0%**)
- **Hindi RAG Retrieval (Baseline):**
  - Hit@1: **0.0%**, Hit@5: **26.7%**, MRR: **0.1028** (Direct English embedder cannot match Devanagari script directly without query normalization / cross-lingual routing).
