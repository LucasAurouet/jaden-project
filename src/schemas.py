from datetime import datetime
from pydantic import BaseModel, Field

class ComputeRequest(BaseModel):
    prompt: str
    # Généré par le navigateur (UUID) : la session est créée au premier échange.
    session_id: str = Field(min_length=1, max_length=64)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

class LoginResponse(BaseModel):
    token: str
    user: UserOut

class SessionOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

class LlamaMetrics(BaseModel):
    tg_tokens_per_sec: float | None = None    
    tg_tokens_per_sec_3s: float | None = None   
    pp_tokens_per_sec: float | None = None     
    n_decoded: int | None = None                
    n_prompt_tokens: int | None = None          
    n_total_tokens: int | None = None           
    kv_cache_usage: float | None = None
    graphs_reused: int | None = None
    total_time_ms: float | None = None
    truncated: bool = False

class SystemMetrics(BaseModel):
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    gpu_vram_used_mb: float | None = None
    gpu_vram_total_mb: float | None = None
    gpu_percent: float | None = None
    gpu_temp_c: float | None = None
    uptime_seconds: float
    llama: LlamaMetrics