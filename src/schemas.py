from pydantic import BaseModel
from typing import Any


# ── API ──────────────────────────────────────────────────────────────────────

class ComputeRequest(BaseModel):
    prompt: str
    expert_type: str


# ── Streaming events (client-side) ───────────────────────────────────────────

class TextEvent(BaseModel):
    type: str = "text"
    node: str
    content: str


class MetricsEvent(BaseModel):
    type: str = "metrics"
    node: str
    data: dict[str, Any]


class ErrorEvent(BaseModel):
    type: str = "error"
    node: str
    error: str


# ── Performance summary (CLI display) ────────────────────────────────────────

class PerfSummary(BaseModel):
    node: str
    expert: str
    t_s: str
    count: str
    ttft: str
    load: str
    net: str
    total: str
    hardware: str


# ── Vote ─────────────────────────────────────────────────────────────────────

class ExpertResponse(BaseModel):
    node: str
    expert: str
    response: str