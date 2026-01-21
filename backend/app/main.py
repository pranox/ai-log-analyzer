# backend/app/main.py

import os
import uuid
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from .github import post_pr_comment
from .llm import run_llm
from .preprocess import extract_relevant_lines, summarize_metadata
from .storage import store_log_bytes, get_log_bytes, ensure_bucket
from .embeddings import index_chunks, retrieve_top_k
from .incidents import save_incident, list_incidents, get_incident
from .failure_detector import extract_failure_block
from .language_detector import detect_language
from .fingerprint import extract_failure_signature
from .lineage import update_lineage
from .lineage import list_lineages, get_lineage
from .confidence import calculate_confidence
from .regression import detect_regression
from .incidents import save_incident
from .confidence import calculate_confidence
from .lineage import update_lineage
from .language_detector import detect_language
from .failure_detector import (
    extract_failure_block,
    extract_failure_signature,
)
from .incident_index import index_incident_summary
from .clusters import assign_cluster
from .clusters import list_clusters

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



async def analyze_log_text(
    raw_text: str,
    incident_id: str,
    repo: str | None = None,
    pr_number: int | None = None,
) -> dict:
    regression = None
    # --------------------------------------------------
    # SAFETY
    # --------------------------------------------------
    if not isinstance(raw_text, str):
        raw_text = json.dumps(raw_text, indent=2)

    logger.info("Analyzing incident_id=%s", incident_id)

    # --------------------------------------------------
    # STEP 1: FAILURE SIGNAL DETECTION (HARD GATE)
    # --------------------------------------------------
    failure_block = extract_failure_block(raw_text)
    metadata = summarize_metadata(raw_text)
    language = detect_language(raw_text)
    # ---- ensure mandatory metadata keys ----
    metadata.setdefault("fingerprint", "UNKNOWN")
    metadata.setdefault("exception", "UNKNOWN")
    metadata.setdefault("failing_line", "UNKNOWN")

    metadata["language"] = language

    failure_sig = extract_failure_signature(raw_text, language)
    metadata["fingerprint"] = failure_sig.get("fingerprint", "UNKNOWN")
    metadata["exception"] = failure_sig.get("exception", "UNKNOWN")
    metadata["failing_line"] = failure_sig.get("failing_line", "UNKNOWN")

    cluster_id = assign_cluster(
    incident_id=incident_id,
    fingerprint = metadata.get("fingerprint", "UNKNOWN"),
    language=language,
    exception=metadata["exception"],
)

    metadata["cluster_id"] = cluster_id

    metadata.update({
        "fingerprint": failure_sig.get("fingerprint"),
        "exception": failure_sig.get("exception"),
        "failing_line": failure_sig.get("failing_line"),
    })

    logger.info(
        "Fingerprint=%s Exception=%s",
        metadata["fingerprint"],
        metadata["exception"],
    )

    # --------------------------------------------------
    # NO FAILURE FOUND → EXIT EARLY (IMPORTANT)
    # --------------------------------------------------
    if not failure_block:
        logger.warning("No failure signal detected for incident %s", incident_id)

        llm_analysis = "NO FAILURE SIGNAL FOUND IN LOGS."

        confidence = calculate_confidence(
            raw_log=raw_text,
            llm_output=llm_analysis,
        )

        save_incident(
            incident_id=incident_id,
            metadata=metadata,
            llm_analysis=llm_analysis,
            confidence=confidence,
            regression_of=regression["matched_incident"] if regression else None,
        )

        update_lineage(
            fingerprint=metadata["fingerprint"],
            incident_id=incident_id,
            repo=repo,
            language=language,
        )

        return {
            "incident_id": incident_id,
            "metadata": metadata,
            "llm_analysis": llm_analysis,
            "confidence": confidence,
            "regression": None,
        }

    # --------------------------------------------------
    # STEP 2: PREPROCESS FAILURE CONTENT ONLY
    # --------------------------------------------------
    reduced = extract_relevant_lines(failure_block)

    # --------------------------------------------------
    # STEP 3: VECTOR INDEXING
    # --------------------------------------------------
    collection_name = f"{DEFAULT_COLLECTION_PREFIX}_{incident_id}"
    index_chunks(reduced, collection=collection_name)

    retrieved = retrieve_top_k(
        "Summarize the failure and suggest fixes",
        collection=collection_name,
        k=5,
    )

    # --------------------------------------------------
    # STEP 4: CONTEXT BUILDING
    # --------------------------------------------------
    context_blocks = [
        f"[CHUNK {i + 1}]\n{item['chunk']}"
        for i, item in enumerate(retrieved)
        if item.get("chunk")
    ]

    context = "\n\n".join(context_blocks)

    # --------------------------------------------------
    # STEP 5: ANTI-HALLUCINATION PROMPT
    # --------------------------------------------------
    prompt = f"""
You are a CI failure analyzer.

LANGUAGE: {language.upper()}

STRICT RULES:
- Analyze ONLY errors related to {language}.
- Quote the EXACT exception name from the log.
- Quote the EXACT failing line or operation.
- If no exception exists, say EXACTLY: "NO EXPLICIT ERROR FOUND".
- Do NOT guess.
- Do NOT invent causes.

LOG:
{context}

TASK:
Explain the failure and suggest fixes.
"""
  
    if failure_sig["exception"] == "UNKNOWN":
      llm_analysis = "NO EXPLICIT ERROR FOUND"
    else:
     llm_analysis = run_llm(prompt)
    logger.info("LLM RESPONSE:\n%s", llm_analysis)

    # --------------------------------------------------
    # STEP 6: CONFIDENCE + REGRESSION
    # --------------------------------------------------
    confidence = calculate_confidence(
        raw_log=raw_text,
        llm_output=llm_analysis,
    )

    regression = detect_regression(
        incident_id=incident_id,
        summary=llm_analysis,
    )

    # --------------------------------------------------
    # STEP 7: PERSIST INCIDENT
    # --------------------------------------------------
    save_incident(
        incident_id=incident_id,
        metadata=metadata,
        llm_analysis=llm_analysis,
        confidence=confidence,
        regression_of=regression["matched_incident"] if regression else None,
    )
    index_incident_summary(incident_id, llm_analysis)
    update_lineage(
        fingerprint=metadata["fingerprint"],
        incident_id=incident_id,
        repo=repo,
        language=language,
    )

    # --------------------------------------------------
    # STEP 8: PR COMMENT BOT (OPTIONAL)
    # --------------------------------------------------
    if repo and pr_number:
        regression_block = ""

        if regression:
            regression_block = f"""
### 🔁 Regression Detected
This failure matches incident `{regression['matched_incident']}`
(Similarity: {regression['similarity']:.2f})
"""

        comment = f"""
🚨 **CI Failure Analysis**

**Incident ID:** `{incident_id}`

### 🧠 Root Cause
{llm_analysis}

### 📊 Confidence
{confidence['level']} ({confidence['score']}%)

{regression_block}

---
_AI-generated. Please review before applying._
"""
        post_pr_comment(repo, pr_number, comment)

    # --------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------
    return {
        "incident_id": incident_id,
        "metadata": metadata,
        "llm_analysis": llm_analysis,
        "confidence": confidence,
        "regression": regression,
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
@app.get("/lineage")
def list_error_lineages():
    return {
        "count": len(list_lineages()),
        "lineages": list_lineages(),
    }
@app.get("/lineage/{fingerprint}")
def get_error_lineage(fingerprint: str):
    lineage = get_lineage(fingerprint)
    if not lineage:
        raise HTTPException(status_code=404, detail="Fingerprint not found")
    return lineage

from .clusters import list_clusters

@app.get("/clusters")
def get_clusters():
    return {
        "count": len(list_clusters()),
        "clusters": list_clusters(),
    }
