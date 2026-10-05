import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Clé partagée entre le serveur et ses clients.
MAIA_KEY: str = os.getenv("MAIA_KEY", "")

# ─── Serveur d'inférence (machine GPU) ──────────────────────────────────────
SERVER_NAME: str = os.getenv("SERVER_NAME", "unknown-node")

# Interface sur laquelle écouter. 0.0.0.0 = toutes (réseau local + localhost).
BIND_HOST: str = os.getenv("BIND_HOST", "0.0.0.0")

# llama-server, joignable uniquement depuis la machine GPU.
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080")
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))

# ─── Client (poste de travail) ──────────────────────────────────────────────
# Adresse du serveur d'inférence à contacter (SERVER_PORT sert aussi
# de port d'écoute au serveur).
SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8081"))

# Port de l'interface web locale (toujours servie sur 127.0.0.1).
CLIENT_PORT: int = int(os.getenv("CLIENT_PORT", "8090"))

# Workspace de l'agent, sur le poste du client.
WORKSPACE_DIR: Path = Path(
    os.getenv("WORKSPACE_DIR", str(Path.home() / "Documents" / "maia"))
).expanduser()
