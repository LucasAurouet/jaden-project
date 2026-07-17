import httpx
from typing import List, Dict
import re
import httpx
from src.schemas import LlamaMetrics

_last_llama_metrics = LlamaMetrics()

async def run_inference(
    messages : List[Dict[str, str]],
    url: str
) -> str:

    payload = {
        "messages": messages
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"]

    except httpx.ConnectError:
        return "[Erreur] Impossible de se connecter au serveur llama.cpp. Vérifiez que le serveur est bien lancé et que le port est correct."
        
    except httpx.TimeoutException:
        return "[Erreur] Le serveur llama.cpp a mis trop de temps à répondre (Timeout)."
        
    except httpx.HTTPStatusError as e:
        return f"[Erreur HTTP {e.response.status_code}] Le serveur a renvoyé une erreur : {e.response.text}"
        
    except (KeyError, ValueError):
        return "[Erreur] La réponse du serveur n'est pas au format attendu."
        
    except Exception as e:
        return f"[Erreur inattendue] {str(e)}"


async def get_llama_metrics_from_api() -> LlamaMetrics:
    """Requête /metrics Prometheus de llama-server."""
    global _last_llama_metrics
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(f"http://127.0.0.1:8080/metrics")
            if r.status_code != 200:
                return _last_llama_metrics

            text = r.text
            def extract(key: str) -> float | None:
                m = re.search(rf"^{re.escape(key)}\s+([\d.]+)", text, re.MULTILINE)
                return float(m.group(1)) if m else None

            kv_ratio = extract("llamacpp:kv_cache_usage_ratio")
            if kv_ratio is not None:
                _last_llama_metrics.kv_cache_hit = kv_ratio

    except Exception:
        pass 

    return _last_llama_metrics