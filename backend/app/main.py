# backend/app/main.py
import os
import uuid
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from .llm import run_llm
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

async def analyze_log_text(raw_text: str, incident_id: str):
    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"

    reduced = extract_relevant_lines(raw_text)
    metadata = summarize_metadata(raw_text)

    index_result = index_chunks(reduced, collection=collection_name)
    retrieved = retrieve_top_k(
        "Summarize the failure and suggest fixes",
        collection=collection_name,
        k=5
    )

    llm_analysis = None
    if retrieved:
        context_blocks = [
            f"[CHUNK {i+1}]\n{item['chunk']}"
            for i, item in enumerate(retrieved)
            if item.get("chunk")
        ]

        llm_prompt = f"""
You are an expert CI/CD debugging assistant.

LOG CONTEXT:
{chr(10).join(context_blocks)}

TASK:
Explain the failure and suggest fixes.
"""
        llm_analysis = run_llm(llm_prompt)

    return {
        "incident_id": incident_id,
        "metadata": metadata,
        "retrieved_top_k": retrieved,
        "llm_analysis": llm_analysis,
    }


@app.get("/")
def root():
    return {"message": "AI Log Analyzer Backend Running"}


@app.post("/webhook/ci")
async def ci_webhook(request: Request):
    """
    CI webhook endpoint.
    Expects failure logs from CI system.
    Automatically triggers analysis + LLM.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    # Minimal contract for now
    raw_text = payload.get("log_text")
    if not raw_text:
        raise HTTPException(status_code=400, detail="log_text missing")

    incident_id = payload.get("incident_id") or str(uuid.uuid4())

    analysis = await analyze_log_text(raw_text, incident_id)

    return JSONResponse({
        "status": "analysis_completed",
        "analysis": analysis
    })



from .llm import run_llm

@app.post("/analyze")
async def analyze(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json payload")

    raw_text = None
    stored_key = None
    incident_id = payload.get("incident_id") or str(uuid.uuid4())

    if "log_text" in payload and payload["log_text"]:
        raw_text = payload["log_text"]

        if payload.get("store", False):
            key = f"{incident_id}.log"
            store_log_bytes(raw_text.encode(), key, bucket=LOGS_BUCKET)
            stored_key = key

    elif "log_key" in payload and payload["log_key"]:
        raw_bytes = get_log_bytes(payload["log_key"], bucket=LOGS_BUCKET)
        raw_text = raw_bytes.decode()
        stored_key = payload["log_key"]

    else:
        raise HTTPException(status_code=400, detail="provide log_text or log_key")

    # 🔥 Single call replaces ALL analysis logic
    result = await analyze_log_text(raw_text, incident_id)
    result["stored_key"] = stored_key

    return JSONResponse(result)
