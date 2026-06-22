# ==========================================
# LE ROUTEUR
# ==========================================
async def route_to_peer(client, peer_url, prompt, expert_type):
    headers = {"X-MAIA-Token": SECRET_KEY}
    payload = {"prompt": prompt, "expert_type": expert_type}
    
    try:
        response = await client.post(peer_url, json=payload, headers=headers, timeout=45.0)
        if response.status_code == 200:
            data = response.json()
            return data.get("node"), data.get("response")
        return peer_url, f"Erreur Réseau ({response.status_code})"
    except Exception as e:
        return peer_url, f"Nœud injoignable ({e})"
