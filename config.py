import os
from dotenv import load_dotenv

load_dotenv()

# Clé partagée entre le serveur et ses clients.
HOMN_KEY: str = os.getenv("HOMN_KEY", "")

# ─── Serveur d'inférence (machine GPU) ──────────────────────────────────────
SERVER_NAME: str = os.getenv("SERVER_NAME", "unknown-node")

# Interface sur laquelle écouter. 0.0.0.0 = toutes (réseau local + localhost).
BIND_HOST: str = os.getenv("BIND_HOST", "0.0.0.0")

# Fournisseur du LLM : toute API compatible OpenAI (llama-server local,
# https://api.mistral.ai...). Le chemin /v1/... est ajouté par le serveur.
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
# Requis par les API hébergées, ignoré par llama-server.
LLM_MODEL: str = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))
# Taille max (estimée) de l'historique envoyé au LLM ; au-delà, les anciens
# tours sont résumés. Environ la moitié du n_ctx : le reste sert au prompt
# système, aux résultats des tools et à la réponse.
CONTEXT_TOKEN_BUDGET: int = int(os.getenv("CONTEXT_TOKEN_BUDGET", "8000"))

# Fournisseur des embeddings (RAG), compatible OpenAI (/v1/embeddings) :
# llama-server lancé avec --embedding, mistral-embed...
EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:8082")
EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "")
# Fixée à la création de la table : changer de modèle impose de réindexer.
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))
# Similarité cosinus minimale d'un passage renvoyé par search_documents
# (0 = pas de seuil). Dépend du modèle d'embeddings : à calibrer à l'aide des
# scores affichés dans les résultats.
RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.5"))

# Postgres avec l'extension pgvector : historique et documents.
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://homn:homn@127.0.0.1:5432/homn")

# ─── Client (poste de travail) ──────────────────────────────────────────────
# Adresse du serveur d'inférence à contacter (SERVER_PORT sert aussi
# de port d'écoute au serveur).
SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8081"))

# Port de l'interface web locale (toujours servie sur 127.0.0.1).
CLIENT_PORT: int = int(os.getenv("CLIENT_PORT", "8090"))

