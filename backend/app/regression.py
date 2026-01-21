from .embeddings import retrieve_top_k
import logging

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85

def detect_regression(incident_id: str, summary: str):
    try:
        matches = retrieve_top_k(
            query=summary,
            collection="incidents_history",
            k=3,
        )
    except Exception as e:
        logger.warning("Regression detection skipped: %s", e)
        return None

    for match in matches:
        if match.get("score", 0) >= SIMILARITY_THRESHOLD:
            return {
                "matched_incident": match["payload"].get("incident_id"),
                "similarity": match["score"],
            }

    return None
