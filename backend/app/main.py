# backend/app/main.py
import os
import uuid
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from .preprocess import extract_relevant_lines, summarize_metadata
from .storage import store_log_bytes, get_log_bytes, ensure_bucket
from .embeddings import index_chunks, retrieve_top_k

app = FastAPI(title="AI Log Analyzer Backend (wired POC)")
logging.basicConfig(level=logging.INFO)

# config (can be overridden via env)
LOGS_BUCKET = os.getenv("LOGS_BUCKET", "logs")
DEFAULT_COLLECTION_PREFIX = os.getenv("COLLECTION_PREFIX", "logs")

# ensure storage bucket exists on startup
try:
    ensure_bucket(LOGS_BUCKET)
except Exception as e:
    logging.warning("Could not ensure logs bucket: %s", e)


@app.get("/")
def root():
    return {"message": "AI Log Analyzer Backend Running"}


@app.post("/webhook/ci")
async def ci_webhook(request: Request):
    """
    Receive CI webhook. If payload contains `log_text` or `log_url` (or artifact URL),
    optionally store the raw log in MinIO and return an incident id and stored key.
    For POC, this endpoint echoes back metadata and stores if log_text provided.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    incident_id = str(uuid.uuid4())
    resp = {"incident_id": incident_id, "received": True, "payload_summary": {}}

    # If log_text provided, store it
    if "log_text" in payload and payload["log_text"]:
        raw_bytes = payload["log_text"].encode("utf-8", errors="replace")
        key = f"{incident_id}.log"
        try:
            store_log_bytes(raw_bytes, key, bucket=LOGS_BUCKET)
            resp["stored_log_key"] = key
        except Exception as e:
            logging.exception("failed to store provided log_text")
            resp["store_error"] = str(e)

    # If there is a log_url, we don't download here in POC (you can later implement download)
    if "log_url" in payload:
        resp["note"] = "log_url received but not auto-downloaded in POC"

    return JSONResponse(resp)


@app.post("/analyze")
async def analyze(request: Request):
    """
    Analyze endpoint (POC wiring):
    - accepts JSON with either {"log_text": "..."} or {"log_key": "<minio-key>"}
    - runs preprocessing (extract_relevant_lines)
    - indexes reduced text into Qdrant (collection named with incident id)
    - retrieves top-k chunks for a simple query
    - returns preprocessed snippet, metadata, indexed count, retrieved chunks

    Note: This POC recreates the collection per call for simplicity (dev only).
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    # Accept either raw text or key
    raw_text = None
    stored_key = None
    incident_id = payload.get("incident_id") or str(uuid.uuid4())
    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"

    if "log_text" in payload and payload["log_text"]:
        raw_text = payload["log_text"]
        # Optionally store raw log in MinIO if user asked
        if payload.get("store", False):
            try:
                key = f"{incident_id}.log"
                store_log_bytes(raw_text.encode("utf-8", errors="replace"), key, bucket=LOGS_BUCKET)
                stored_key = key
            except Exception as e:
                logging.exception("failed to store log_text to minio")
                # continue — storage failure shouldn't block local analysis
    elif "log_key" in payload and payload["log_key"]:
        # fetch from MinIO
        try:
            raw_bytes = get_log_bytes(payload["log_key"], bucket=LOGS_BUCKET)
            raw_text = raw_bytes.decode("utf-8", errors="replace")
            stored_key = payload["log_key"]
        except Exception as e:
            logging.exception("failed to fetch log_key from minio")
            raise HTTPException(status_code=500, detail=f"failed to retrieve log_key: {e}")
    else:
        raise HTTPException(status_code=400, detail="provide log_text or log_key in JSON body")

    # 1) Preprocess
    reduced = extract_relevant_lines(raw_text)
    metadata = summarize_metadata(raw_text)

    # 2) Index reduced text into Qdrant (collection per incident for POC)
    try:
        index_result = index_chunks(reduced, collection=collection_name)
        indexed_count = index_result.get("count", 0)
    except Exception as e:
        logging.exception("indexing failed")
        # continue but report failure
        indexed_count = 0
        index_error = str(e)
    else:
        index_error = None

    # 3) Retrieve top-k chunks for a simple query (RAG proof)
    try:
        retrieved = retrieve_top_k("Summarize the failure and suggest fixes", collection=collection_name, k=5)
    except Exception as e:
        logging.exception("retrieval failed")
        retrieved = []
        retrieval_error = str(e)
    else:
        retrieval_error = None

    # 4) Build response
    resp = {
        "incident_id": incident_id,
        "stored_key": stored_key,
        "collection": collection_name,
        "reduced_preview": reduced[:2000],
        "reduced_length": len(reduced),
        "metadata": metadata,
        "indexed_count": indexed_count,
        "index_error": index_error,
        "retrieved_top_k": retrieved,
        "retrieval_error": retrieval_error,
        "note": "No LLM was called. Use retrieved_top_k as RAG context for LLM in next step."
    }

    return JSONResponse(resp)
