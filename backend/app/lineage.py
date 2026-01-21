from datetime import datetime
from typing import Dict

# In-memory MVP store (replace with DB later)
LINEAGE_STORE: Dict[str, dict] = {}

def update_lineage(
    fingerprint: str,
    incident_id: str,
    repo: str | None,
    language: str,
):
    now = datetime.utcnow().isoformat() + "Z"

    if fingerprint not in LINEAGE_STORE:
        LINEAGE_STORE[fingerprint] = {
            "fingerprint": fingerprint,
            "first_seen": now,
            "last_seen": now,
            "occurrence_count": 1,
            "incident_ids": [incident_id],
            "repos": set([repo]) if repo else set(),
            "languages": set([language]),
        }
    else:
        entry = LINEAGE_STORE[fingerprint]
        entry["last_seen"] = now
        entry["occurrence_count"] += 1
        entry["incident_ids"].append(incident_id)
        if repo:
            entry["repos"].add(repo)
        entry["languages"].add(language)

def get_lineage(fingerprint: str) -> dict | None:
    entry = LINEAGE_STORE.get(fingerprint)
    if not entry:
        return None

    # convert sets to lists for JSON
    return {
        **entry,
        "repos": list(entry["repos"]),
        "languages": list(entry["languages"]),
    }

def list_lineages():
    return [
        {
            **entry,
            "repos": list(entry["repos"]),
            "languages": list(entry["languages"]),
        }
        for entry in LINEAGE_STORE.values()
    ]
