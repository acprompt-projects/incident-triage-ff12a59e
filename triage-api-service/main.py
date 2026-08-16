import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Incident Triage Service", version="0.1.0")

# --- In-memory store ---
incidents_db: dict[str, dict] = {}

# --- Enums ---
class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"

class IncidentStatus(str, Enum):
    open = "open"
    triaging = "triaging"
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"

class SourceType(str, Enum):
    rules_engine = "rules_engine"
    manual = "manual"
    monitoring = "monitoring"

# --- Pydantic models ---
class AlertPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)
    source: SourceType = SourceType.rules_engine
    severity_hint: Optional[Severity] = None
    tags: list[str] = Field(default_factory=list)
    correlation_key: Optional[str] = None

class IncidentCreate(AlertPayload):
    pass

class IncidentOut(BaseModel):
    id: str
    title: str
    description: str
    source: SourceType
    severity: Severity
    status: IncidentStatus
    tags: list[str]
    correlation_key: Optional[str]
    created_at: datetime
    updated_at: datetime

class TriageUpdate(BaseModel):
    severity: Optional[Severity] = None
    status: Optional[IncidentStatus] = None
    tags: Optional[list[str]] = None
    assignee: Optional[str] = None

# --- Classification helper ---
def classify_severity(title: str, description: str, hint: Optional[Severity]) -> Severity:
    if hint:
        return hint
    text = (title + " " + description).lower()
    if any(w in text for w in ["outage", "down", "data loss", "breach"]):
        return Severity.critical
    if any(w in text for w in ["degraded", "partial", "failover"]):
        return Severity.high
    if any(w in text for w in ["slow", "retry", "warning"]):
        return Severity.medium
    return Severity.low

# --- Deduplication / correlation ---
def find_existing_incident(correlation_key: Optional[str]) -> Optional[str]:
    if not correlation_key:
        return None
    for inc_id, inc in incidents_db.items():
        if inc["correlation_key"] == correlation_key and inc["status"] in (
            IncidentStatus.open, IncidentStatus.triaging,
        ):
            return inc_id
    return None

# --- Endpoints ---
@app.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(payload: IncidentCreate):
    existing_id = find_existing_incident(payload.correlation_key)
    if existing_id:
        raise HTTPException(status_code=409, detail=f"Correlated incident already exists: {existing_id}")

    now = datetime.now(timezone.utc)
    severity = classify_severity(payload.title, payload.description, payload.severity_hint)
    inc_id = str(uuid.uuid4())

    incident = {
        "id": inc_id,
        "title": payload.title,
        "description": payload.description,
        "source": payload.source,
        "severity": severity,
        "status": IncidentStatus.open,
        "tags": payload.tags,
        "correlation_key": payload.correlation_key,
        "assignee": None,
        "created_at": now,
        "updated_at": now,
    }
    incidents_db[inc_id] = incident
    return IncidentOut(**incident)

@app.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str):
    incident = incidents_db.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentOut(**incident)

@app.patch("/incidents/{incident_id}/triage", response_model=IncidentOut)
def update_triage(incident_id: str, update: TriageUpdate):
    incident = incidents_db.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident["status"] in (IncidentStatus.resolved, IncidentStatus.closed):
        raise HTTPException(status_code=422, detail="Cannot triage a resolved/closed incident")

    if update.severity:
        incident["severity"] = update.severity
    if update.status:
        incident["status"] = update.status
    if update.tags is not None:
        incident["tags"] = update.tags
    if update.assignee:
        incident["assignee"] = update.assignee
    incident["updated_at"] = datetime.now(timezone.utc)

    return IncidentOut(**incident)

@app.get("/health")
def health():
    return {"status": "ok", "incidents_count": len(incidents_db)}