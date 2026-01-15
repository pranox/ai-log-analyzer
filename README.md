# AI Log Analyzer 🔍🤖

AI Log Analyzer is a backend DevOps tool that automatically analyzes CI/CD failure logs.
Instead of manually reading long logs, the system preprocesses errors, retrieves relevant
context using embeddings, and generates clear explanations and fixes using a remote LLM.

The system is backend-first, CI-agnostic, and designed to work even on low-spec machines.

---

## 🚀 Key Features

- CI/CD webhook for automatic failure analysis
- Log preprocessing to extract only error-relevant lines
- Semantic retrieval using embeddings (RAG)
- Remote LLM inference (Ollama) over private VPN (Tailscale)
- Retry & timeout handling for network resilience
- Safe design (no automatic code changes)

---

## 🧠 High-Level Architecture

CI Failure
↓
POST /webhook/ci
↓
Preprocessing (error extraction)
↓
Embeddings + Vector DB (Qdrant)
↓
Relevant chunk retrieval (RAG)
↓
Remote LLM (Ollama via Tailscale)
↓
Explanation + Fix Suggestions

yaml
Copy code

---

## 📦 Tech Stack

- **Backend**: FastAPI (Python)
- **Vector DB**: Qdrant
- **Object Storage**: MinIO
- **Embeddings**: Sentence Transformers
- **LLM**: Ollama (remote machine)
- **Networking**: Tailscale (private VPN)

---

## 🔧 Environment Setup

Create a `.env` file (DO NOT commit this):

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_SECURE=false

QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=all-MiniLM-L6-v2

LLM_URL=http://<REMOTE_LLM_TAILSCALE_IP>:11434/api/generate
LLM_MODEL=llama3

yaml
Copy code

---

## ▶️ Running the Backend

```bash
uvicorn backend.app.main:app --reload --port 8000
## Deployment Mode: Tailscale-based LLM

In this mode, the AI Log Analyzer connects to a remote LLM server
over a private Tailscale network. This allows running LLMs on a
separate machine without exposing public ports.
