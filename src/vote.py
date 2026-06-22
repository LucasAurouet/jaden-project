# ==========================================
# LE JUGE
# ==========================================
async def ask_juge_consensus(prompt_original, expert_responses):
    print("\n[Juge] ⚖️ Arbitrage et fusion des réponses en cours...")
    
    context = ""
    for node, text in expert_responses:
        context += f"--- AVIS DE L'EXPERT [{node}] ---\n{text}\n\n"
        
    prompt_juge = f"""
    Tu es l'arbitre du système MAIA. Synthétise les réponses des experts pour répondre au prompt initial.
    Corrige les erreurs, garde la rigueur technique, fusionne la logique de code et la clarté de rédaction.
    
    PROMPT INITIAL : {prompt_original}
    
    {context}
    
    RÉPONSE FINALE CONSENSUS :
    """
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(f"{JUGE_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": prompt_juge,
                "stream": False
            }, timeout=60.0)
            return res.json().get("response")
        except Exception as e:
            return f"Erreur critique du service Juge : {e}"