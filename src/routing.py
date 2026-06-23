import os
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

MAIA_KEY = os.getenv("MAIA_KEY")
NODE_NAME = os.getenv("NODE_NAME")

async def route_to_peer(client: httpx.AsyncClient, url: str, prompt: str, expert_type: str):
    """
    Générateur asynchrone pur. Ne contient AUCUN 'print' ou 'sys.stdout.write'.
    Génère des dictionnaires d'événements pour le consommateur (le CLI).
    """
    payload = {"prompt": prompt, "expert_type": expert_type}
    headers = { "maia-token": MAIA_KEY}
    
    try:
        async with client.stream("POST", f"http://{url}/v1/compute", json=payload, timeout=None, headers=headers) as response:
            response.raise_for_status()
            
            async for chunk in response.aiter_text():
                if not chunk:
                    continue
        
                if "|||" in chunk:
                    parts = chunk.split("|||")
                    if parts[0].strip():
                        yield {"type": "text", "node": NODE_NAME, "content": parts[0]}
                    
                    try:
                        perf_metrics = json.loads(parts[1])
                        yield {"type": "metrics", "node": NODE_NAME, "data": perf_metrics}
                    except Exception:
                        pass
                else:
                    yield {"type": "text", "node": NODE_NAME, "content": chunk}
                    
    except Exception as e:
        yield {"type": "error", "node": NODE_NAME, "error": str(e)}
