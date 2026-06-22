import os
import asyncio
import httpx
from src.routing import route_to_peer
from src.vote import vote_best_answer
from dotenv import load_dotenv

load_dotenv()

PEERS_IP = os.getenv("PEERS_IP", "")

async def start_cli():
    print("="*60)
    print("      M.A.I.A. - Cli Interface      ")
    print("="*60)
    
    peers = [ip.strip() for ip in PEERS_IP.split(",") if ip]
    if not peers:
        raise ValueError("0 pairs disponibles.")
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
                expert_responses = await asyncio.gather(*tasks, return_exceptions=True)
                print(f"responses: {expert_responses}")
                for node, _ in expert_responses:
                    print(f" └─ [Récolte] Réponse reçue de [{node}]")
                
                final_output = await vote_best_answer(prompt, expert_responses)
                
                print("\n[MAIA SYNTHÈSE FINALE] :")
                print(final_output)
                print("-" * 60)
                
            except KeyboardInterrupt:
                break