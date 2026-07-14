from config import SERVER_IP
import httpx

async def run_query(prompt):
    url = f"http://{SERVER_IP}/v1/compute"
    
    payload = {"prompt": prompt}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

            response.raise_for_status()

            data = response.json()
            return data
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