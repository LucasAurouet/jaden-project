import os
from dotenv import load_dotenv

load_dotenv()

# Node identity
NODE_NAME: str = os.getenv("NODE_NAME", "unknown-node")
NODE_PORT: int = int(os.getenv("NODE_PORT", "8000"))

# Auth
MAIA_KEY: str = os.getenv("MAIA_KEY", "")

# Ollama
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Client
PEERS_IP: list[str] = [
    ip.strip()
    for ip in os.getenv("PEERS_IP", "").split(",")
    if ip.strip()
]