import httpx

async def run_inference(
    prompt: str,
    url: str
) -> str:

    payload = {
        "messages": [
            {"role": "assistant", "content":  "you are a helpful assistant"},
            {"role": "user", "content": f"{prompt}"}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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

