async def cli_interface():
    print("="*60)
    print("      M.A.I.A. Core - Production Ready Orchestrator      ")
    print("="*60)
    print(f"[Réseau] {len(PEERS)} nœuds d'inférence détectés dans le fichier de config.\n")

    # On attribue un rôle expert à chaque nœud pour le MVP de manière cyclique
    expert_roles = ["code", "maths", "writing"]

    async with httpx.AsyncClient() as client:
        while True:
            try:
                prompt = input("\nMAIA App 🦚 > ")
                if prompt.lower() == 'q':
                    break
                if not prompt.strip():
                    continue
                
                # ROUTING PARALLÈLE
                print("[Routeur] Dispatch de la requête vers l'essaim...")
                tasks = [
                    route_to_peer(client, url, prompt, expert_roles[i % len(expert_roles)]) 
                    for i, url in enumerate(PEERS)
                ]
                expert_responses = await asyncio.gather(*tasks)
                
                # Log de débogage propre
                for node, resp in expert_responses:
                    print(f"\n[Récolte] [{node}] a répondu.")
                
                # JUGE CONSENSUS
                final_output = await ask_juge_consensus(prompt, expert_responses)
                
                print("\n✨ [MAIA SYNTHÈSE FINALE] :")
                print(final_output)
                print("-" * 60)
                
            except KeyboardInterrupt:
                break