# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Jaden**: a natural-language assistant for Yu-Gi-Oh! that answers questions about cards, decks and combos. It is a reference and analysis tool, **not** a duel simulator: no game engine, no Konami assets (card art, UI, sounds).

Jaden started from the skeleton of **Maia** (`upstream` remote = `git@github.com:LucasAurouet/maia.git`, branch `dev`): a self-hosted assistant (LLM chat + tool calling + RAG). Python/FastAPI, two processes: an inference **server** (GPU machine, local LLM through llama-server) and a web **client**. The two projects have diverged (squashed migrations, no document upload, renamed modules), so `upstream` is **not** merged: a useful maia fix is brought over with `git cherry-pick <commit>`, resolving conflicts by hand.

Code comments, docstrings and user-facing messages are written in French; keep that convention. Commit messages are in English and prefixed `feature:`, `fix:`, `hotfix:` or `refactor:`.

## Jaden roadmap (not built yet)

**Audience**: a casual player and fan of the anime, not a competitive one. Priorities: understanding cards, rules and how a deck plays. Banlists, the current meta and tournament data are out of scope for now.

1. **Card database**: sync the public YGOPRODeck API (`https://db.ygoprodeck.com/api/v7/`, English + French) into Postgres through an Alembic migration and an ingestion command (`python main.py sync-cards`). Never call the API per user request. Its rules: 20 requests/s max (exceeding it means a 1-hour block), store all data locally, and **download each card image once and serve it ourselves**: hotlinking `images.ygoprodeck.com` gets the IP blacklisted. Alternate artworks have their own ids, which `.ydk` files may use.
2. **Card tools** in `TOOLS` (`src/api/services/tools.py`): `search_cards` (structured filters: type, attribute, level/rank/link, race, archetype, ATK/DEF, plus full-text over the effect), `get_card`, `get_archetype`, `parse_decklist` (`.ydk` / plain text). Tool results are compact text, not raw JSON, because a local model's context is small.
3. **Rules RAG**: a small, clean corpus explaining the game rules (chains, summon mechanics, timing), indexed with `python main.py index`.
4. **Anime RAG** (optional): characters, their decks, anime-only cards. Yugipedia is CC BY-SA: usable with attribution.

- **The model never states a card fact from memory**: effects and stats always come from a tool. The system prompt enforces it. Combos are not in the API: the model reasons from the effect texts it fetched. Hand-written combo notes can be indexed as RAG documents.
- **Local model constraints**: tool calling depends on the llama-server chat template (`--jinja`). Prefer few, well-described tools with flat parameters. `MAX_TOOL_ITERATIONS` (3) will probably need raising for multi-card questions.
- **React frontend** (Vite + TypeScript, strict mode) replaces `src/client/static` (vanilla JS). The client FastAPI process stays the relay, auth cookie included, and serves the built bundle. The React app keeps talking to `/api/*` only. It adds a panel for the cards cited in an answer and a deck import.

## Commands

```bash
pip install -r requirements.txt      # a venv/ already exists at the repo root
python main.py server                # backend on BIND_HOST:SERVER_PORT (default 0.0.0.0:8081)
python main.py client                # web UI on http://127.0.0.1:CLIENT_PORT (default 8090)
python main.py adduser <name> [--admin]   # create an account (also: passwd <name>, deluser <name>)
python main.py index <file>...       # index reference documents for the RAG (also: documents, unindex <id>)
python main.py sync-cards [--force]  # update the card database from YGOPRODeck (skipped if its version is unchanged)
pwsh scripts/start-llama.ps1         # dev only: starts the chat + embeddings llama-server instances
```

There is no test suite, linter or build step. Accounts are created by the admin with the CLI only (no sign-up). Reference documents are indexed with the CLI only too: there is no upload from the web interface.

The server needs a reachable Postgres with the pgvector extension (`DATABASE_URL`). On startup, `init_db` applies the pending Alembic migrations (`alembic upgrade head`, run in a thread), then opens the asyncpg pool and checks the embedding dimension.

**Schema changes go through Alembic migrations, never through `init_db`.** The history starts from a single `initial_schema` migration (Maia's migrations were squashed), so a Maia database cannot be reused: Jaden needs its own database. There is no ORM: migrations are raw SQL (`op.execute`), so `--autogenerate` is not used. Migrations live in `src/api/migrations/versions/`, and `env.py` reads `DATABASE_URL` from `config.py` (with the `postgresql+asyncpg` driver). A migration that has been applied somewhere is never edited: write a new one instead.

```bash
alembic revision -m "add tool_trace to messages"   # new empty migration, then write upgrade()/downgrade()
alembic upgrade head                               # apply (the server also does this on startup)
alembic downgrade -1                               # undo the last migration
alembic current / alembic history                  # where the database stands
alembic upgrade head --sql                         # print the SQL without touching the database
```

## Configuration

All settings come from `.env`, read in `config.py`, which is the single source of truth (with defaults). The key settings:
- `JADEN_KEY`: machine key for the raw OpenAI-compatible proxy only (`/v1/chat/completions`, `/v1/models`, checked by `verify_token`). Users authenticate with their account instead.
- `AUTH_TOKEN_TTL_DAYS`: lifetime of a login token (default 30).
- `COOKIE_SECURE`: send the client's session cookie over HTTPS only. Set it to true behind the HTTPS reverse proxy.
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`: any OpenAI-compatible provider (local llama-server, Mistral API…). The base URL has no `/v1`, which the code appends.
- `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_DIM`: OpenAI-compatible `/v1/embeddings`. `EMBEDDING_DIM` is fixed in the `chunks` table, and startup fails on a mismatch, so changing models means reindexing.
- `EMBEDDING_QUERY_PREFIX` / `EMBEDDING_PASSAGE_PREFIX`: prepended before embedding, for models trained with them (e5, nomic). Empty for bge-m3 and mistral-embed. Only the vector uses them (`content` stays raw), and changing the passage prefix means reindexing.
- `RAG_MIN_SCORE`: minimum cosine similarity for a passage returned by `search_documents` (0 = no threshold, default 0.5). Score distributions depend on the embedding model, so calibrate it from the scores shown in results.
- `RAG_AUTO_SEARCH` / `RAG_AUTO_MIN_SCORE`: automatic retrieval before every answer (default on, threshold 0.7, stricter than `RAG_MIN_SCORE` since no model judges relevance).
- `RAG_HYBRID_SEARCH`: hybrid retrieval, vector + BM25 fused by RRF (default on). The thresholds above still apply to the cosine score, but `search_documents` also keeps BM25 hits below `RAG_MIN_SCORE`.
- `CONTEXT_TOKEN_BUDGET`: estimated token budget (4 chars/token) for the session history sent to the LLM. Above it, old exchanges are summarized (about half of `n_ctx` is a good value).
- `SERVER_IP` / `SERVER_PORT`: where the client finds the server. `SERVER_PORT` is also the server's listen port.
- `LLAMA_*` keys: read only by `scripts/start-llama.ps1`. That script derives the llama-server ports from `LLM_BASE_URL` / `EMBEDDING_BASE_URL`, which must be loopback.

## Architecture

```
browser (src/client/static, vanilla JS) ──/api/*──▶ client (src/client/web.py)
    ──/v1/* + Bearer <user token>──▶ server (src/api/server.py)
    ──▶ LLM provider (/v1/chat/completions) + embedding provider (/v1/embeddings) + Postgres/pgvector
```

- **The client is a thin relay.** `src/client/services/jaden.py` forwards `/api/*` (login, sessions, compute, metrics) to the server. It has no database or agent logic, and all state lives server-side. It is meant to be shared: it runs next to the server, behind an HTTPS reverse proxy, and every user logs in.
- **Auth**: password login (argon2, `src/api/services/auth.py`). `POST /v1/auth/login` returns an opaque token, and only its SHA-256 is stored in `auth_tokens`, with an expiry. Logout or `passwd` delete the rows, which revokes them at once. `get_current_user` (`dependencies.py`) resolves the Bearer token to a user on every request. The client keeps the token in an `HttpOnly`, `SameSite=Strict` cookie (`jaden_session`, `src/client/dependencies.py`) and sends it as Bearer, so the page's JS never sees it.
- **Per-user data**: every query filters by user. `sessions.user_id` owns a conversation, and a session owned by someone else is treated as missing (404). The browser generates the session id (UUID, kept in the URL `#id` so a reload restores it). The session row is created on the first saved exchange, with the start of the prompt as title. `GET/DELETE /v1/sessions…` list, read and delete them. Reference documents (RAG) are not per-user: they are shared by all and managed by the admin from the CLI. Tools receive `user_id` from `execute_tool`, never from the model.
- **The agent loop is server-side**, in `src/api/services/chat.py`. `POST /v1/compute` loads the session history from Postgres, prepends `SYSTEM_PROMPT` and calls the LLM with `TOOL_SCHEMAS`. It runs tool calls for up to `MAX_TOOL_ITERATIONS` (3) iterations, then forces a final answer with no tools. The LLM is always called with `stream: true`, and the response is an SSE stream of JSON events: `delta` (text chunk), `tool` (tool being called), `status` (other progress message), then `done` or `error`. The client relays this stream as is to the browser. History is bounded by a rolling summary: `sessions.summary` replaces every message with `id <= sessions.summary_upto`, and it is merged into the system prompt. When the summary and the remaining messages exceed `CONTEXT_TOKEN_BUDGET`, `_build_context` summarizes the oldest exchanges in bounded batches and keeps the recent ones (~40% of the budget) verbatim. It emits a `status` event first. If summarizing fails, those exchanges are only left out for that turn. Raw messages are never deleted. The exchange is saved (`save_exchange`, user prompt + all streamed text) only once the answer is complete: an interrupted or failed answer is not saved. Intermediate tool messages exist only in memory.
- **Tools** are registered in the `TOOLS` dict in `src/api/services/tools.py` (async function, description and JSON-Schema parameters), and `TOOL_SCHEMAS` is derived from it. `execute_tool` never raises: errors come back as text so the model can retry. To add a tool, add an entry there.
- **RAG** lives in `src/api/services/rag.py`, for both indexing and retrieval. `rag.ingest` (called by `python main.py index`) checks the extension (text formats only) and rejects a file whose content is already indexed (`documents.sha256`, unique). Only the content counts: two different files with the same name are both kept. It splits the text into paragraph-grouped chunks (`CHUNK_SIZE`/`CHUNK_OVERLAP` in characters), embeds them in batches (`embeddings.py`) and stores them in `documents`/`chunks`, which have an HNSW cosine index. Retrieval is `rag.search`: in hybrid mode it runs the vector search (k nearest) and a BM25 search side by side, then fuses them by Reciprocal Rank Fusion (ranks only, since cosine and BM25 scores are not comparable). BM25 is computed in SQL (`database.search_chunks_bm25`) over `chunks.tsv`, a generated `tsvector` (`french` config) with a GIN index: query terms are OR-ed, so IDF weights rare terms. Every result keeps its cosine `score`, and `bm25` if BM25 found it. The `search_documents` tool calls it and applies `RAG_MIN_SCORE`. On top of that, `stream_compute` runs `auto_search` on the raw prompt before every answer: up to 3 passages above `RAG_AUTO_MIN_SCORE` are appended to the user message for that call only (not the system prompt, to keep llama-server's prefix cache; never saved). It never raises, so an embedding outage does not block the chat.
- **Raw OpenAI-compatible proxy**: `src/api/routers/inference.py` streams `/v1/chat/completions` and `/v1/models` straight to the LLM provider, behind the Jaden key, with no agent or tools.
- **Upstream HTTP**: each upstream (LLM, embeddings, client→server) has a module-level `httpx.AsyncClient` created and closed in the FastAPI `lifespan`. Upstream failures are mapped to domain exceptions (`UpstreamUnavailable`/`UpstreamTimeout` become 502/504 in `server.py`, and `InferenceError` becomes an SSE `error` event).
- **Metrics**: `/v1/metrics/all` combines psutil/NVML system stats with llama-server's Prometheus `/metrics`. The llama-server stats are empty for other providers. The chat llama-server must run with `--jinja` (tool calling) and `--metrics`.
- Shared Pydantic models live in `src/schemas.py`.
- **Card database** (Yu-Gi-Oh-specific code lives in `src/api/cards/`): `sync.py` downloads all cards from YGOPRODeck in English and French (3 requests, skipped when `checkDBVer` is unchanged, stored in `sync_state`) and replaces the data in one transaction. Skill cards and tokens are left out. `cards` holds one row per card (API codes such as `type`/`race`/`attribute` stay in English, `atk`/`def` = -1 means "?", the full API answer minus prices is in `raw`). `card_artworks` maps every artwork id (`.ydk` files may use them) to its card. The French translation is matched by any artwork id, then by English name, because both languages do not always pick the same main id. Name lookup uses `pg_trgm` on `name_key_en`/`name_key_fr` (normalized by `cards/text.py`: lowercase, no accents or punctuation); in SQL, wrap comparisons on the nullable `name_key_fr` in `coalesce`, or NULLs sort first. Effects are searchable through the generated `search_en`/`search_fr` tsvectors. The model is given English effect texts (precise PSCT wording) and both names.

## Référence
- ~/hdd/open-webui (v0.12.3) est une référence de conception, en lecture seule.
- Quand je demande comment Open WebUI fait quelque chose, va lire son code
  (points d'entrée : backend/open_webui/models, routers, utils/middleware.py, retrieval/).
- Ne recopie jamais son code : explique le principe et adapte-le à notre architecture.
