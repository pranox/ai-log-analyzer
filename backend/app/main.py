# backend/app/main.py

import os
import uuid
import logging
import json
import base64
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .llm import run_llm
from .preprocess import extract_relevant_lines, summarize_metadata
from .storage import store_log_bytes, get_log_bytes, ensure_bucket
from .embeddings import index_chunks, retrieve_top_k

# --------------------------------------------------
# ENV + APP SETUP
# --------------------------------------------------

load_dotenv()  # ✅ IMPORTANT: load .env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Log Analyzer Backend")

LOGS_BUCKET = os.getenv("LOGS_BUCKET", "logs")
DEFAULT_COLLECTION_PREFIX = os.getenv("COLLECTION_PREFIX", "logs")

# --------------------------------------------------
# OPTIONAL STORAGE INIT (non-blocking)
# --------------------------------------------------

try:
    ensure_bucket(LOGS_BUCKET)
except Exception as e:
    logger.warning("Could not ensure logs bucket: %s", e)

# --------------------------------------------------
# CORE ANALYSIS PIPELINE (shared logic)
# --------------------------------------------------

async def analyze_log_text(raw_text: str, incident_id: str) -> dict:
    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"

    logger.info("Analyzing incident_id=%s", incident_id)

    reduced = extract_relevant_lines(raw_text)
    metadata = summarize_metadata(raw_text)

    index_chunks(reduced, collection=collection_name)

    retrieved = retrieve_top_k(
        "Summarize the failure and suggest fixes",
        collection=collection_name,
        k=5
    )

    llm_analysis = None
    if retrieved:
        context_blocks = [
            f"[CHUNK {i + 1}]\n{item['chunk']}"
            for i, item in enumerate(retrieved)
            if item.get("chunk")
        ]

        prompt = f"""
You are an expert CI/CD debugging assistant.

LOG CONTEXT:
{chr(10).join(context_blocks)}

TASK:
Explain the failure and suggest fixes.
"""

        llm_analysis = run_llm(prompt)

    return {
        "incident_id": incident_id,
        "metadata": metadata,
        "retrieved_top_k": retrieved,
        "llm_analysis": llm_analysis,
    }

# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/")
def root():
    return {"message": "AI Log Analyzer Backend Running"}

# --------------------------------------------------
# CI WEBHOOK (AUTOMATED ENTRY POINT)
# --------------------------------------------------

import json
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse

@app.post("/webhook/ci")
async def ci_webhook(request: Request):
    logger.info(">>> CI WEBHOOK HIT <<<")

    body = await request.body()

    # 1️⃣ Guard: empty body
    if not body:
        logger.error("Empty request body received from CI")
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "empty body"}
        )

    # 2️⃣ Guard: invalid JSON
    try:
        payload = json.loads(body)
    except Exception:
        logger.error("Invalid JSON from CI: %s", body)
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "invalid json"}
        )

    # 3️⃣ Guard: missing log
    log_text = payload.get("log_text")
    if not log_text:
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "empty log"}
        )

    incident_id = payload.get("incident_id") or str(uuid.uuid4())

    analysis = await analyze_log_text(log_text, incident_id)

    return {
        "status": "analysis_completed",
        "incident_id": incident_id,
        "analysis": analysis
    }

# --------------------------------------------------
# MANUAL ANALYZE ENDPOINT (DEBUG / UI)
# --------------------------------------------------

@app.post("/analyze")
async def analyze(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    incident_id = payload.get("incident_id") or str(uuid.uuid4())
    raw_text = None
    stored_key = None

    if payload.get("log_text"):
        raw_text = payload["log_text"]

        if payload.get("store", False):
            key = f"{incident_id}.log"
            store_log_bytes(raw_text.encode(), key, bucket=LOGS_BUCKET)
            stored_key = key

    elif payload.get("log_key"):
        raw_bytes = get_log_bytes(payload["log_key"], bucket=LOGS_BUCKET)
        raw_text = raw_bytes.decode()
        stored_key = payload["log_key"]

    else:
        raise HTTPException(status_code=400, detail="provide log_text or log_key")

    # ✅ SAFETY (important)
    if raw_text is not None and not isinstance(raw_text, str):
        raw_text = json.dumps(raw_text, indent=2)

    result = await analyze_log_text(raw_text, incident_id)
    result["stored_key"] = stored_key

    return JSONResponse(result)
