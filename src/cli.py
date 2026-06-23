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
                expert_outputs = await asyncio.gather(*tasks, return_exceptions=True)

                valid_responses = []
                for output in expert_outputs:
                    if isinstance(output, Exception):
                        print(f" └─ [Erreur Réseau] Un des nœuds est injoignable : {output}")
                        continue
                    
                    node_name = output.get("node", "Agent Inconnu")
                    expert_type = output.get("expert", "généraliste")
                    response_text = output.get("response", "")
                    performance = output.get("performance", {}) 

                    print(f" └─ [Récolte] Réponse de [{node_name}] ({expert_type})")
                    if telemetry:
                        print(f"    └── ⏱️  {performance.get('vitesse_tokens_sec')} t/s | Latence Réseau: {telemetry.get('temps_reseau_overhead_sec')}s")

                    valid_responses.append(output)

                if valid_responses:
                    final_output = await vote_best_answer(prompt, valid_responses)
                    
                    print("\n[MAIA SYNTHÈSE FINALE] :")
                    print(final_output)
                    print("-" * 60)
                else:
                    print("\n[Échec Total] Aucun agent n'a pu répondre.")
                
            except KeyboardInterrupt:
                break