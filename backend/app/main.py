# backend/app/main.py

import os
import uuid
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .llm import run_llm
from .preprocess import extract_relevant_lines, summarize_metadata
from .storage import store_log_bytes, get_log_bytes, ensure_bucket
from .embeddings import index_chunks, retrieve_top_k
from .incidents import save_incident, list_incidents, get_incident

# ==================================================
# ENV + APP SETUP
# ==================================================

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-log-analyzer")

app = FastAPI(title="AI Log Analyzer Backend")

LOGS_BUCKET = os.getenv("LOGS_BUCKET", "logs")
DEFAULT_COLLECTION_PREFIX = os.getenv("COLLECTION_PREFIX", "logs")

# ==================================================
# STORAGE INIT (NON-BLOCKING)
# ==================================================

try:
    ensure_bucket(LOGS_BUCKET)
except Exception as e:
    logger.warning("Could not ensure logs bucket: %s", e)

# ==================================================
# CORE ANALYSIS PIPELINE
# ==================================================

async def analyze_log_text(raw_text: str, incident_id: str) -> dict:
    """
    Shared analysis logic used by both CI webhook and manual API.
    """

    # SAFETY: ensure string
    if not isinstance(raw_text, str):
        raw_text = json.dumps(raw_text, indent=2)

    logger.info("Analyzing incident_id=%s", incident_id)

    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"

    # ---- preprocessing ----
    reduced = extract_relevant_lines(raw_text)
    metadata = summarize_metadata(raw_text)

    # ---- embeddings / indexing ----
    index_chunks(reduced, collection=collection_name)

    retrieved = retrieve_top_k(
        "Summarize the failure and suggest fixes",
        collection=collection_name,
        k=5,
    )

    # ---- LLM ----
    context_blocks = []
    for i, item in enumerate(retrieved):
        if item.get("chunk"):
            context_blocks.append(f"[CHUNK {i + 1}]\n{item['chunk']}")

    prompt = f"""
You are an expert CI/CD debugging assistant.

LOG CONTEXT:
{chr(10).join(context_blocks) if context_blocks else reduced}

TASK:
1. Explain the root cause.
2. Suggest concrete fixes.
3. Mention assumptions if needed.
"""

    llm_analysis = run_llm(prompt)
    logger.info("LLM RESPONSE:\n%s", llm_analysis)

     # ---- persist incident ----
    save_incident(
        incident_id=incident_id,
        metadata=metadata,
        llm_analysis=llm_analysis,
    )

    return {
        "incident_id": incident_id,
        "metadata": metadata,
        "retrieved_top_k": retrieved,
        "llm_analysis": llm_analysis,
    }

# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/")
def root():
    return {"status": "ok", "service": "AI Log Analyzer"}

# ==================================================
# CI WEBHOOK ENDPOINT
# ==================================================

@app.post("/webhook/ci")
async def ci_webhook(request: Request):
    """
    Entry point for CI systems.
    Must NEVER fail the pipeline.
    """

    logger.info(">>> CI WEBHOOK HIT <<<")

    body = await request.body()

    # ---- guard: empty body ----
    if not body:
        logger.warning("Empty request body received from CI")
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "empty body"},
        )

    # ---- guard: invalid JSON ----
    try:
        payload = json.loads(body)
    except Exception:
        logger.warning("Invalid JSON received from CI")
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "invalid json"},
        )

    log_text = payload.get("log_text")
    if not log_text:
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "no log_text"},
        )

    incident_id = payload.get("incident_id") or str(uuid.uuid4())

    try:
        analysis = await analyze_log_text(log_text, incident_id)
    except Exception as e:
        logger.exception("Analysis failed")
        return JSONResponse(
            status_code=200,
            content={"status": "analysis_failed", "error": str(e)},
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "analysis_completed",
            "incident_id": incident_id,
            "analysis": analysis,
        },
    )

# ==================================================
# MANUAL ANALYZE ENDPOINT (DEBUG / UI)
# ==================================================

@app.post("/analyze")
async def analyze(request: Request):
    """
    Manual API for testing or UI usage.
    """

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
        raise HTTPException(
            status_code=400,
            detail="provide log_text or log_key",
        )

    result = await analyze_log_text(raw_text, incident_id)
    result["stored_key"] = stored_key

    return JSONResponse(result)

@app.get("/incidents")
def get_incidents():
    """
    List all analyzed incidents.
    """
    return {
        "count": len(list_incidents()),
        "incidents": list_incidents(),
    }
@app.get("/incidents/{incident_id}")
def get_incident_by_id(incident_id: str):
    """
    Get full details for a single incident.
    """
    incident = get_incident(incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return incident
