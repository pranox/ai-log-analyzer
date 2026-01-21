# AI Log Analyzer for CI/CD Failure Intelligence

## Project Status
**Phase-1 Completed (v1.1-incidents)**  
Core CI automation, AI-based log analysis, and incident history implemented.

---

## Problem Statement
CI/CD pipelines generate large failure logs that are time-consuming to debug manually.
This project builds an automated backend service that analyzes CI failures and produces
clear explanations and fix suggestions using AI.

---

## System Architecture
- CI Systems (GitHub Actions)
- FastAPI Backend
- Failure Detection & Preprocessing
- Vector Indexing (Qdrant)
- LLM Analysis (RAG)
- Incident History Store

---

## Implemented Features (Phase-1)
- CI webhook for automated log ingestion
- Failure signal detection & noise removal
- Language detection (Python, Java, Node.js)
- Error fingerprinting & clustering
- Vector-based semantic retrieval (Qdrant)
- LLM-based failure explanation
- Confidence scoring
- Incident history API

---

## Tech Stack
- Backend: FastAPI (Python)
- Vector DB: Qdrant
- Object Storage: MinIO
- Embeddings: Sentence Transformers
- LLM: Remote LLM (via Tailscale / API)
- CI: GitHub Actions

---

## How the System Works
1. CI failure triggers webhook
2. Logs are preprocessed and filtered
3. Relevant chunks are vectorized
4. Context is retrieved using semantic search
5. LLM generates explanation and fixes
6. Incident is stored for future reference

---

## Sample Results
- Python ValueError → Correct fix suggestion
- Java NullPointerException → Accurate explanation
- Clean logs → No false positives

---

## API Endpoints
- POST /webhook/ci
- POST /analyze
- GET /incidents
- GET /incidents/{id}

---

## Known Limitations (Phase-1)
- In-memory incident storage
- No frontend UI
- Partial regression detection

---

## Roadmap (Phase-2)
- Persistent database
- Full regression detection
- Frontend dashboard
- Alerting & analytics
