from config import SERVER_IP, SERVER_PORT, MAIA_KEY
import httpx
import uuid

_CURRENT_SESSION_ID = str(uuid.uuid4())

def get_current_session_id() -> str:
    """Permet à l'UI de savoir quel est l'ID actuel si elle en a besoin (ex: pour l'afficher)."""
    return _CURRENT_SESSION_ID

def start_new_session() -> str:
    """Force la création d'une nouvelle session (ex: bouton 'Nouveau Chat' dans l'UI)."""
    global _CURRENT_SESSION_ID
    _CURRENT_SESSION_ID = str(uuid.uuid4())
    return _CURRENT_SESSION_ID

async def run_query(prompt, session_id: str = None) -> str:
    if session_id is None:
            session_id = str(uuid.uuid4())

    url = f"http://{SERVER_IP}:{SERVER_PORT}/v1/compute"
    
    payload = {"prompt": prompt,
               "session_id": _CURRENT_SESSION_ID}

    headers = {"maia-token": MAIA_KEY} 
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            response.raise_for_status()

            data = response.json()
            return data.get("response", "[Erreur] Format de réponse invalide")
    except httpx.ConnectError:
        return f"[Erreur] Impossible de se connecter au serveur d'inférence ({SERVER_IP}). Vérifiez que le serveur est bien lancé et que l'IP est correcte."
    
    except httpx.TimeoutException:
        return f"[Erreur] Le serveur d'inférence ({SERVER_IP}) a mis trop de temps à répondre (Timeout)."
        
    except httpx.HTTPStatusError as e:
        return f"[Erreur HTTP {e.response.status_code}] Le serveur a renvoyé une erreur : {e.response.text}"
        
    except (KeyError, ValueError):
        return "[Erreur] La réponse du serveur n'est pas au format attendu."
        
    except Exception as e:
        return f"[Erreur inattendue] {str(e)}"