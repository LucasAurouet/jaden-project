from pydantic import BaseModel
from typing import Any


# ── API ──────────────────────────────────────────────────────────────────────

class ComputeRequest(BaseModel):
    prompt: str

