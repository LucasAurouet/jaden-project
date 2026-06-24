"""
Responsabilité unique : transformer un chunk final Ollama en dict de métriques
propres, et construire le PerfSummary destiné à l'affichage.
"""

import time
import psutil
from src.schemas import PerfSummary


def parse_ollama_metrics(chunk: dict, node_name: str, expert_type: str, t0: float) -> dict:
    httpx_time = time.time() - t0
    total_dur = chunk.get("total_duration", 0)
    eval_dur  = chunk.get("eval_duration", 0)
    eval_count = chunk.get("eval_count", 0)

    return {
        "node":   node_name,
        "expert": expert_type,
        "performance": {
            "tokens_sec":       round(eval_count / (eval_dur / 1e9), 2) if eval_dur else 0,
            "token_count":      eval_count,
            "total_time":       round(total_dur / 1e9, 2),
            "loading_time":     round(chunk.get("load_duration", 0) / 1e9, 2),
            "ttft":             round(chunk.get("prompt_eval_duration", 0) / 1e9, 2),
            "eval_time":        round(eval_dur / 1e9, 2),
            "network_overhead": round(max(0, httpx_time - total_dur / 1e9), 2),
            "cpu_usage":        psutil.cpu_percent(interval=None),
            "ram_usage":        psutil.virtual_memory().percent,
        },
    }


def to_perf_summary(perf: dict, expert_type: str) -> PerfSummary:
    p = perf.get("performance", perf)
    gpu_str = (
        f" G:{p['gpu_usage']}% V:{p['gpu_ram']}%"
        if "gpu_usage" in p else ""
    )
    return PerfSummary(
        node=perf.get("node", "?"),
        expert=expert_type,
        t_s=f"{p.get('tokens_sec', 0):.1f} t/s",
        count=f"{p.get('token_count', 0)} tkn",
        ttft=f"{p.get('ttft', 0):.2f}s",
        load=f"{p.get('loading_time', 0):.1f}s",
        net=f"{p.get('network_overhead', 0):.2f}s",
        total=f"{p.get('total_time', 0):.1f}s",
        hardware=f"C:{p.get('cpu_usage', 0)}% R:{p.get('ram_usage', 0)}%{gpu_str}",
    )