from datetime import datetime
from typing import Dict, List, Any
import uuid

# In-memory cluster store (MVP)
_CLUSTERS: Dict[str, Dict[str, Any]] = {}

SIMILARITY_THRESHOLD = 0.88


def find_cluster_by_fingerprint(fingerprint: str) -> str | None:
    for cluster_id, cluster in _CLUSTERS.items():
        if fingerprint in cluster["fingerprints"]:
            return cluster_id
    return None


def create_cluster(
    incident_id: str,
    fingerprint: str,
    language: str,
    exception: str | None,
) -> str:
    cluster_id = f"cluster-{uuid.uuid4().hex[:8]}"

    _CLUSTERS[cluster_id] = {
        "cluster_id": cluster_id,
        "primary_incident": incident_id,
        "incident_ids": [incident_id],
        "fingerprints": {fingerprint},
        "languages": {language},
        "exceptions": {exception} if exception else set(),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_seen": datetime.utcnow().isoformat() + "Z",
    }

    return cluster_id


def add_incident_to_cluster(
    cluster_id: str,
    incident_id: str,
    fingerprint: str,
    language: str,
    exception: str | None,
):
    cluster = _CLUSTERS[cluster_id]

    cluster["incident_ids"].append(incident_id)
    cluster["fingerprints"].add(fingerprint)
    cluster["languages"].add(language)

    if exception:
        cluster["exceptions"].add(exception)

    cluster["last_seen"] = datetime.utcnow().isoformat() + "Z"


def assign_cluster(
    incident_id: str,
    fingerprint: str,
    language: str,
    exception: str | None,
) -> str:
    """
    Returns cluster_id
    """

    # 1️⃣ Exact fingerprint match (fast, deterministic)
    existing = find_cluster_by_fingerprint(fingerprint)
    if existing:
        add_incident_to_cluster(
            existing,
            incident_id,
            fingerprint,
            language,
            exception,
        )
        return existing

    # 2️⃣ Otherwise → create new cluster
    return create_cluster(
        incident_id,
        fingerprint,
        language,
        exception,
    )


def list_clusters() -> List[Dict[str, Any]]:
    return list(_CLUSTERS.values())
