# backend/app/incidents.py

from datetime import datetime
from typing import Dict, List, Any, Optional

# --------------------------------------------------
# In-memory incident store (MVP)
# --------------------------------------------------

_INCIDENTS: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------
# Public API
# --------------------------------------------------

def save_incident(
    incident_id: str,
    metadata: Dict[str, Any],
    llm_analysis: str,
    confidence: Optional[Dict[str, Any]] = None,
    regression_of: Optional[str] = None,
):
    """
    Persist an analyzed incident.
    """

    _INCIDENTS[incident_id] = {
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata,
        "summary": _extract_summary(llm_analysis),
        "llm_analysis": llm_analysis,
        "confidence": confidence,
        "regression_of": regression_of,
    }


def list_incidents() -> List[Dict[str, Any]]:
    """
    Return all incidents (newest first).
    """
    return sorted(
        _INCIDENTS.values(),
        key=lambda x: x["timestamp"],
        reverse=True,
    )


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single incident by ID.
    """
    return _INCIDENTS.get(incident_id)


# --------------------------------------------------
# Regression helper (Step 6)
# --------------------------------------------------

def find_similar_incident(
    summary: str,
    threshold: float = 0.8,
) -> Optional[str]:
    """
    Very lightweight regression detector (MVP).

    For now:
    - compares summaries by overlap
    - later replaced by vector search (Qdrant)

    Returns incident_id if similar found.
    """

    if not summary:
        return None

    summary_tokens = set(summary.lower().split())

    for incident in _INCIDENTS.values():
        prev_summary = incident.get("summary", "")
        if not prev_summary:
            continue

        prev_tokens = set(prev_summary.lower().split())

        overlap = len(summary_tokens & prev_tokens)
        similarity = overlap / max(len(summary_tokens), 1)

        if similarity >= threshold:
            return incident["incident_id"]

    return None


# --------------------------------------------------
# Internal helpers
# --------------------------------------------------

def _extract_summary(llm_text: str, max_len: int = 200) -> str:
    """
    Extract a short summary from LLM output.
    """
    if not llm_text:
        return "No summary available"

    text = llm_text.strip().replace("\n", " ")
    return text[:max_len] + ("..." if len(text) > max_len else "")
