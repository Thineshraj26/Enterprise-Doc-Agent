# Enterprise Document Intelligence & Compliance Agent (Full-Stack RAG)

A production-grade, local enterprise document analysis agent built with strict data-layer Role-Based Access Control (RBAC), deterministic factual grounding, and an immutable audit trail.

---

## Key Features

- **Data-Layer RBAC Enforcement:** Chunks are pre-filtered at the vector database layer using PostgreSQL JSONB containment (`WHERE allowed_roles::jsonb ? :role`). Unauthorized cross-department queries return 0 chunks before invoking the LLM, eliminating prompt injection risks and LLM token usage.
- **Deterministic Factual Grounding:** Employs programmatic regular-expression verification against retrieved chunk IDs (`[chunk_id]`), guaranteeing verified source attribution and preventing hallucinations.
- **Cost & Latency Optimization:** Embeds documents locally using ONNX runtime and `BAAI/bge-small-en-v1.5` (384-d), completely eliminating embedding egress costs.
- **Resilient Model Failover:** Implements automated fallback routing with exponential backoff across Google AI Studio models to handle transient 503 spikes and daily quota limits.
- **Immutable Audit Trail:** Append-only logging of user IDs, roles, vector queries, accessed chunk IDs, and timestamps.
- **Full-Stack Web Interface:** Single-page dashboard supporting drag-and-drop file ingestion (`.pdf`, `.docx`, `.txt`), real-time role switching, grounded Q&A, and an auditor portal.

---

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL 17 with `pgvector` (via Docker Compose)
- **Embeddings:** FastEmbed (`BAAI/bge-small-en-v1.5`, ONNX Runtime)
- **Inference:** Google GenAI SDK (`gemini-2.5-flash`, `gemini-flash-latest`)
- **Frontend:** Vanilla JS, HTML5, Tailwind CSS

---

## Getting Started

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/)
- Python 3.12+
- Google AI Studio API Key

### 2. Database Setup
Start the PostgreSQL container with `pgvector` enabled:
\`\`\`bash
docker compose up -d
\`\`\`

### 3. Environment Setup
\`\`\`bash
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY
\`\`\`

### 4. Run the Application
\`\`\`bash
uvicorn app.main:app --port 8000
\`\`\`

Navigate to `http://127.0.0.1:8000` to access the web UI.

### 5. Run the Automated Test Suite
\`\`\`bash
python test_api.py
\`\`\`