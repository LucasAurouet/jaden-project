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
                
                print("[Routeur] Envoi de la requête vers les agents...")
                tasks = [
                    route_to_peer(client, url, prompt, expert_roles[i % len(expert_roles)]) 
                    for i, url in enumerate(peers)
                ]
                expert_outputs = await asyncio.gather(*tasks, return_exceptions=True)

                valid_responses = []
                perf_metrics = []

                for output in expert_outputs:
                    if isinstance(output, Exception):
                            print(f" └─ [Erreur Système] : {output}")
                            continue
                    
                    node_name = output.get("node", "Agent")
                    expert_type = output.get("expert", "inconnu")
                    response_text = output.get("response", "")
                    performance = output.get("performance", {}) 
                    print(f"[Récolte] Réponse de [{node_name}] ({expert_type})")
                    
                    if "error" in output:
                        print(f"[Échec] Noeud [{node_name}] ({expert_type}) -> {output['error']}")
                        continue

                    valid_responses.append(output)

                    if performance:
                        perf_metrics.append({
                            "node": node_name,
                            "expert": expert_type,
                            "t_s": f"{performance.get('tokens_sec', 0):.1f} t/s",
                            "ttft": f"{performance.get('ttft', 0):.2f}s",
                            "net": f"{peperformancerf.get('network_overhead', 0):.2f}s",
                            "cpu_ram": f"{performance.get('cpu_usage', 0)}% / {performance.get('ram_usage', 0)}%"
                        })

                    if perf_metrics:
                        print("\n" + "="*80)
                        print(f"{'NŒUD':<15} | {'EXPERT':<10} | {'VITESSE':<10} | {'TTFT':<8} | {'RÉSEAU':<8} | {'CPU/RAM':<12}")
                        print("-"*80)
                        for p in perf_metrics:
                            print(f"{p['node']:<15} | {p['expert']:<10} | {p['t_s']:<10} | {p['ttft']:<8} | {p['net']:<8} | {p['cpu_ram']:<12}")
                        print("="*80 + "\n")

                if valid_responses:
                    final_output = await vote_best_answer(prompt, valid_responses)
                    
                    print("\n[MAIA SYNTHÈSE FINALE] :")
                    print(final_output)
                    print("-" * 60)
                else:
                    print("\n[Échec Total] Aucun agent n'a pu répondre.")
                
            except KeyboardInterrupt:
                break