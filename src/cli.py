import os
import asyncio
import httpx
from src.routing import route_to_peer
from src.vote import vote_best_answer
from dotenv import load_dotenv
import sys

load_dotenv()

PEERS_IP = os.getenv("PEERS_IP", "")
NODE_NAME = os.getenv("NODE_NAME", "Agent")

async def consume_agent_stream(client, url, prompt, expert_type, valid_responses, perf_metrics):
    full_text = ""

    async for event in route_to_peer(client, url, prompt, expert_type):
        if event["type"] == "text":
            text_chunk = event["content"]
            full_text += text_chunk
            
            # C'est le CLI qui gère le formatage visuel !
            clean_text = text_chunk.replace('\n', f'\n[{NODE_NAME}] ')
            sys.stdout.write(clean_text)
            sys.stdout.flush()
            
        elif event["type"] == "metrics":
            perf = event["data"]
            # On enrichit la liste partagée des performances pour le tableau de fin
            perf_metrics.append({
                "node": perf.get("node", NODE_NAME),
                "expert": expert_type,
                "t_s": f"{perf.get('tokens_sec', 0):.1f} t/s",
                "count": f"{perf.get('token_count', 0)} tkn",
                "ttft": f"{perf.get('ttft', 0):.2f}s",
                "load": f"{perf.get('loading_time', 0):.1f}s",
                "net": f"{perf.get('network_overhead', 0):.2f}s",
                "total": f"{perf.get('total_time', 0):.1f}s",
                "hardware": f"C:{perf.get('cpu_usage', 0)}% R:{perf.get('ram_usage', 0)}%" + \
                            (f" G:{perf.get('gpu_usage')}% V:{perf.get('gpu_ram')}%" if 'gpu_usage' in perf else "")
            })
            
        elif event["type"] == "error":
            print(f"\n[Échec] Noeud [{NODE_NAME}] ({expert_type}) -> {event['error']}")
            return

    # Une fois le stream fini avec succès, on enregistre la réponse globale pour le vote
    valid_responses.append({
        "node": NODE_NAME,
        "expert": expert_type,
        "response": full_text
    })

async def start_cli():
    print("="*60 + "\n      M.A.I.A. - Cli Interface      \n" + "="*60)
    peers = [ip.strip() for ip in PEERS_IP.split(",") if ip]
    expert_roles = ["code", "maths", "writing"]

    async with httpx.AsyncClient(timeout=None) as client:
        while True:
            try:
                prompt = input("\nMAIA App > ")
                if prompt.lower() == 'q': 
                    break
                if not prompt.strip(): 
                    continue
                
                print("[Routeur] Démarrage des agents...\n" + "-"*50)
                
                valid_responses = []
                perf_metrics = []
                
                tasks = [
                    consume_agent_stream(client, url, prompt, expert_roles[i % len(expert_roles)], valid_responses, perf_metrics)
                    for i, url in enumerate(peers)
                ]
                await asyncio.gather(*tasks)
                
                print("\n" + "-"*50 + "\n[Routeur] Fin du streaming. Analyse du tableau de bord...")

                # --- ICI : Affichage de ton Tableau de bord (Inchangé) ---
                if perf_metrics:
                    print("\n" + "="*115)
                    print(f"{'NOEUD':<13} | {'EXPERT':<10} | {'VITESSE':<9} | {'VOLUME':<8} | {'TTFT':<7} | {'LOAD':<6} | {'RÉSEAU':<7} | {'TOTAL':<6} | {'MATÉRIEL':<25}")
                    print("-"*115)
                    for p in perf_metrics:
                        print(f"{p['node']:<13} | {p['expert']:<10} | {p['t_s']:<9} | {p['count']:<8} | {p['ttft']:<7} | {p['load']:<6} | {p['net']:<7} | {p['total']:<6} | {p['hardware']:<25}")
                    print("="*115 + "\n")

                if valid_responses:
                    final_output = await vote_best_answer(prompt, valid_responses)
                    print(f"\n[MAIA SYNTHÈSE FINALE] :\n{final_output}\n" + "-" * 60)
                
            except KeyboardInterrupt:
                break