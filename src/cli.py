import os
import asyncio
import httpx
from src.routing import route_to_peer
from src.vote import vote_best_answer

async def start_cli():
    print("="*60)
    print("      M.A.I.A. - Cli Interface      ")
    print("="*60)
    
    peers = [ip.strip() for ip in os.getenv("MAIA_PEER_NODES", "").split(",") if ip]
    print(f"[Réseau] {len(peers)} noeuds d'inférence configurés.\n")
    
    expert_roles = ["code", "maths", "writing"]

    async with httpx.AsyncClient() as client:
        while True:
            try:
                prompt = input("\nMAIA App > ")
                if prompt.lower() == 'q':
                    break
                if not prompt.strip():
                    continue
                
                print("[Routeur] Dispatch de la requête vers l'essaim...")
                tasks = [
                    route_to_peer(client, url, prompt, expert_roles[i % len(expert_roles)]) 
                    for i, url in enumerate(peers)
                ]
                expert_responses = await asyncio.gather(*tasks)
                
                for node, _ in expert_responses:
                    print(f" └─ [Récolte] Réponse reçue de [{node}]")
                
                final_output = await ask_juge_consensus(prompt, expert_responses)
                
                print("\n✨ [MAIA SYNTHÈSE FINALE] :")
                print(final_output)
                print("-" * 60)
                
            except KeyboardInterrupt:
                break