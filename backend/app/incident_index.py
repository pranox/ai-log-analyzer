from .embeddings import index_chunks

def index_incident_summary(incident_id: str, summary: str):
    index_chunks(
        summary,
        collection="incidents_history",
        payload={"incident_id": incident_id},
    )
