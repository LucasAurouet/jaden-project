import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "server"
    
    if mode == "server":
        from config import SERVER_NAME, SERVER_PORT
        import uvicorn
        from src.api.server import app
        print(f"Démarrage du server à l'adresse [{SERVER_NAME}]")
        uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)

    elif mode == "client":
        from src.client.cli import start_cli
        asyncio.run(start_cli())

    else:
        print("Usage: python main.py [server|client]")
        sys.exit(1)