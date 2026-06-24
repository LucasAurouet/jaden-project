import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "client"

    if mode == "server":
        from config import NODE_NAME, NODE_PORT
        import uvicorn
        from src.api.server import app
        print(f"[Agent] Démarrage du noeud [{NODE_NAME}] sur le port {NODE_PORT}...")
        uvicorn.run(app, host="0.0.0.0", port=NODE_PORT)

    elif mode == "client":
        from src.client.orchestrator import run
        asyncio.run(run())

    else:
        print(f"Usage: python main.py [server|client]")
        sys.exit(1)