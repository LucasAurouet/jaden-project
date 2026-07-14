import os
from dotenv import load_dotenv

load_dotenv()

# Node identity
SERVER_NAME: str = os.getenv("SERVER_NAME", "unknown-node")
SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8080"))

# Auth
MAIA_KEY: str = os.getenv("MAIA_KEY", "")
