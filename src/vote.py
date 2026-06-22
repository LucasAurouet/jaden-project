import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434")

async def vote_best_answer(prompt_original, expert_responses):
    context = ""
    for node, text in expert_responses:
        context += f"--- AVIS DE L'EXPERT [{node}] ---\n{text}\n\n"
        
    prompt_vote = f"""
    Tu es l'arbitre du système MAIA. Synthétise les réponses des experts pour répondre au prompt initial.
    Élimine les hallucinations, garde la rigueur technique et fusionne le tout de manière fluide.
    
    PROMPT INITIAL : {prompt_original}
    
    {context}
    
    RÉPONSE FINALE CONSENSUS :
    """
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3:8b",
                "prompt": prompt_vote,
                "stream": False
            }, timeout=60.0)
            return res.json().get("response")
        except Exception as e:
            return f"Erreur critique du service de vote local : {e}"