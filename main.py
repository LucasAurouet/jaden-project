import sys
from config import BIND_HOST, SERVER_PORT, CLIENT_PORT

USAGE = """Usage: python main.py [server|client|cli]
  server  serveur d'inférence (machine GPU)
  client  interface web locale sur http://127.0.0.1:{port}
  cli     client en ligne de commande""".format(port=CLIENT_PORT)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "server"

    if mode == "server":
        import uvicorn
        from src.api.server import app
        print(f"Serveur d'inférence sur {BIND_HOST}:{SERVER_PORT}")
        uvicorn.run(app, host=BIND_HOST, port=SERVER_PORT)

    elif mode == "client":
        import uvicorn
        from src.client.web import app
        print(f"Interface MAIA sur http://127.0.0.1:{CLIENT_PORT}")
        uvicorn.run(app, host="127.0.0.1", port=CLIENT_PORT)

    else:
        print(USAGE)
        sys.exit(1)
