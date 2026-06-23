import os
import httpx
from dotenv import load_dotenv

load_dotenv()

MAIA_KEY = os.getenv("MAIA_KEY")

async def route_to_peer(client: httpx.AsyncClient, peer_url: str, prompt: str, expert_type: str):
    headers = {"maia-token": MAIA_KEY}
    payload = {"prompt": prompt, "expert_type": expert_type}

    try:
        response = await client.post(f"http://{peer_url}/v1/compute", json=payload, headers=headers, timeout=45.0)
        
        if response.status_code == 200:
            return response.json()
            
        return {
            "node": peer_url,
            "expert": expert_type,
            "error": f"Erreur Agent ({response.status_code}) : {response.text}"
        }
        
    except Exception as e:
        return {
            "node": peer_url,
            "expert": expert_type,
            "error": f"Nœud injoignable ({type(e).__name__})"
        }
