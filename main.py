import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "server"
    
    if mode == "server":
        from config import NODE_NAME, NODE_PORT
        import uvicorn
        from src.api.server import app
        print(f"[Agent] Démarrage du noeud [{NODE_NAME}] sur le port {NODE_PORT}...")
        uvicorn.run(app, host="0.0.0.0", port=NODE_PORT)

    elif mode == "client":
        interface = sys.argv[2] if len(sys.argv) > 2 else "cli"

        if interface == "ui":
            from src.client.ui import start_ui
            start_ui()
        elif interface == "cli":
            from src.client.cli import start_cli
            asyncio.run(start_cli())
        else:
            print(f"Usage: python main.py client [ui|cli]")
            sys.exit(1)

    else:
        print("Usage: python main.py [server|client [ui|cli]]")
        sys.exit(1)