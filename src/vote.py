import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

def build_voting_prompt(prompt_original, expert_responses):

    context = ""
    for data in expert_responses:
        node = data.get("node")
        expert = data.get("expert")
        text = data.get("response")
        context += f"--- AVIS DE L'EXPERT [{node}] ---\n{text}\n\n"
        
        prompt_vote = f"""
        Tu es l'arbitre du système MAIA. Synthétise les réponses des experts pour répondre au prompt initial.
        Élimine les hallucinations, garde la rigueur technique et fusionne le tout de manière fluide.
        
        PROMPT INITIAL : {prompt_original}
        
        {context}
        """

    return prompt_vote

async def vote_best_answer(prompt_original, expert_responses):

    prompt_vote = build_voting_prompt(prompt_original, expert_responses)
    
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            res = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": "llama3.2:3b",
                "prompt": prompt_vote,
                "stream": False
            }, timeout=None)
            return res.json().get("response")
        except Exception as e:
            return f"Erreur critique du service de vote local : {type(e).__name__} : {e}"