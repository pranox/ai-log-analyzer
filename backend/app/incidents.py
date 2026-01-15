# backend/app/incidents.py

from datetime import datetime
from typing import Dict, List, Any

# In-memory incident store (MVP)
# Can be replaced with DB later
_INCIDENTS: Dict[str, Dict[str, Any]] = {}


def save_incident(
    incident_id: str,
    metadata: Dict[str, Any],
    llm_analysis: str,
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


def get_incident(incident_id: str) -> Dict[str, Any] | None:
    """
    Get a single incident by ID.
    """
    return _INCIDENTS.get(incident_id)


def _extract_summary(llm_text: str, max_len: int = 200) -> str:
    """
    Extract a short summary from LLM output.
    """
    if not llm_text:
        return "No summary available"

    text = llm_text.strip().replace("\n", " ")
    return text[:max_len] + ("..." if len(text) > max_len else "")
