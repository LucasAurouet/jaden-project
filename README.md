# Jaden

A self-hosted, natural-language assistant for Yu-Gi-Oh!. Ask it about cards, rules, decks and combos: it looks the cards up in a local database and the rules in a reference corpus, then explains.

Jaden is a reference and analysis tool, **not** a duel simulator: no game engine, no Konami assets. Cards and search are in English only.

## How it works

```
browser ──/api/*──▶ client (web UI, thin relay) ──/v1/*──▶ server (agent loop, tools, RAG)
                                                              ├─▶ LLM (any OpenAI-compatible API, e.g. llama-server)
                                                              ├─▶ embeddings (OpenAI-compatible /v1/embeddings)
                                                              └─▶ Postgres + pgvector
```

- **Server** (`python main.py server`): runs on the GPU machine. It holds every piece of state: accounts, conversations, the card database and the rules corpus. It also runs the tool-calling loop against the LLM.
- **Client** (`python main.py client`): serves the web interface on `127.0.0.1` and relays requests to the server. It has no database.

The model never states a card fact from memory: effects and stats come from tools backed by the card database.

## Requirements

- Python 3.10 to 3.13. Python 3.14 is not supported yet: asyncpg 0.30 has no build for it.
- Server only:
  - PostgreSQL with the `pgvector` and `pg_trgm` extensions.
  - An OpenAI-compatible LLM endpoint. With llama-server, start it with `--jinja` (needed for tool calling) and `--metrics`.
  - An OpenAI-compatible embeddings endpoint, for example llama-server with `--embedding` and bge-m3 (1024 dimensions).

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Settings are read from a `.env` file at the repository root. `config.py` lists every key with its default.

**Client machine**: the client only needs to know where the server is.

```ini
SERVER_IP=192.168.1.10
SERVER_PORT=8081
# CLIENT_PORT=8090
# COOKIE_SECURE=true      # behind an HTTPS reverse proxy
```

**Server machine**:

```ini
DATABASE_URL=postgresql://jaden:jaden@127.0.0.1:5432/jaden
LLM_BASE_URL=http://127.0.0.1:8080        # no /v1
LLM_MODEL=                                # required by hosted APIs, ignored by llama-server
EMBEDDING_BASE_URL=http://127.0.0.1:8082
EMBEDDING_DIM=1024
JADEN_KEY=change-me                       # key for the raw /v1/chat/completions proxy
```

Database migrations (Alembic) are applied automatically when the server starts.

## Usage

```bash
# Server machine
python main.py server                     # API on BIND_HOST:SERVER_PORT (default 0.0.0.0:8081)
python main.py adduser <name> [--admin]   # create an account (no sign-up page)
python main.py passwd <name>              # change a password
python main.py deluser <name>             # delete an account
python main.py sync-cards                 # download/update cards from YGOPRODeck and embed them
                                          #   --force, --embed-only, --reembed
python main.py index <file>...            # add reference documents (.md, .txt...) to the rules corpus
python main.py documents                  # list indexed documents
python main.py unindex <id>               # remove one

# Client machine
python main.py client                     # web UI on http://127.0.0.1:8090
```

Users log in with an account created by the admin.

## Status

Done:
- Chat with a server-side agent loop, streamed answers, per-user history with rolling summaries.
- Rules RAG with hybrid search (vectors + BM25).
- Card database synced from YGOPRODeck, with hybrid card search.

Planned:
- Card tools for the model (`search_cards`, `get_card`, `get_archetype`, `parse_decklist`).
- A rules corpus.
- A React frontend with a cited-cards panel and deck import.

## Data sources and credits

- Card data: [YGOPRODeck API](https://ygoprodeck.com/api-guide/). It is synced locally and never queried per request, as its rules require.
- Yu-Gi-Oh! is a trademark of Konami. Jaden is a fan project, not affiliated with or endorsed by Konami.
