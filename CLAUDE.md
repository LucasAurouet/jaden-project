# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Homn Systems: a self-hosted personal assistant (LLM chat + tool calling + RAG). Python/FastAPI, two processes: an inference **server** (GPU machine or VPS) and a local web **client**. Code comments, docstrings and user-facing messages are written in French; keep that convention. Commit messages are in English and prefixed `feature:`, `fix:`, `hotfix:` or `refactor:`.

## Commands

```bash
pip install -r requirements.txt      # a venv/ already exists at the repo root
python main.py server                # backend on BIND_HOST:SERVER_PORT (default 0.0.0.0:8081)
python main.py client                # web UI on http://127.0.0.1:CLIENT_PORT (default 8090)
pwsh scripts/start-llama.ps1         # dev only: starts the chat + embeddings llama-server instances
```

There is no test suite, linter or build step. `main.py` mentions a `cli` mode, but it is not implemented.

The server needs a reachable Postgres with the pgvector extension (`DATABASE_URL`). On startup, `init_db` applies the pending Alembic migrations (`alembic upgrade head`, run in a thread), then opens the asyncpg pool and checks the embedding dimension.

**Schema changes go through Alembic migrations, never through `init_db`.** There is no ORM: migrations are raw SQL (`op.execute`), so `--autogenerate` is not used. Migrations live in `src/api/migrations/versions/`, and `env.py` reads `DATABASE_URL` from `config.py` (with the `postgresql+asyncpg` driver). A migration that has been applied somewhere is never edited: write a new one instead.

```bash
alembic revision -m "add tool_trace to messages"   # new empty migration, then write upgrade()/downgrade()
alembic upgrade head                               # apply (the server also does this on startup)
alembic downgrade -1                               # undo the last migration
alembic current / alembic history                  # where the database stands
alembic upgrade head --sql                         # print the SQL without touching the database
```

## Configuration

All settings come from `.env`, read in `config.py`, which is the single source of truth (with defaults). The key settings:
- `HOMN_KEY`: shared secret. The server checks it as `Authorization: Bearer` (`src/api/dependencies.py:verify_token`), and the client sends it.
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`: any OpenAI-compatible provider (local llama-server, Mistral API…). The base URL has no `/v1`, which the code appends.
- `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_DIM`: OpenAI-compatible `/v1/embeddings`. `EMBEDDING_DIM` is fixed in the `chunks` table, and startup fails on a mismatch, so changing models means reindexing.
- `RAG_MIN_SCORE`: minimum cosine similarity for a passage returned by `search_documents` (0 = no threshold, default 0.5). Score distributions depend on the embedding model, so calibrate it from the scores shown in results.
- `RAG_AUTO_SEARCH` / `RAG_AUTO_MIN_SCORE`: automatic retrieval before every answer (default on, threshold 0.7, stricter than `RAG_MIN_SCORE` since no model judges relevance).
- `RAG_HYBRID_SEARCH`: hybrid retrieval, vector + BM25 fused by RRF (default on). The thresholds above still apply to the cosine score, but `search_documents` also keeps BM25 hits below `RAG_MIN_SCORE`.
- `CONTEXT_TOKEN_BUDGET`: estimated token budget (4 chars/token) for the session history sent to the LLM. Above it, old exchanges are summarized (about half of `n_ctx` is a good value).
- `SERVER_IP` / `SERVER_PORT`: where the client finds the server. `SERVER_PORT` is also the server's listen port.
- `LLAMA_*` keys: read only by `scripts/start-llama.ps1`. That script derives the llama-server ports from `LLM_BASE_URL` / `EMBEDDING_BASE_URL`, which must be loopback.

## Architecture

```
browser (src/client/static, vanilla JS) ──/api/*──▶ client (src/client/web.py)
    ──/v1/* + Bearer HOMN_KEY──▶ server (src/api/server.py)
    ──▶ LLM provider (/v1/chat/completions) + embedding provider (/v1/embeddings) + Postgres/pgvector
```

- **The client is a thin relay.** `src/client/services/homn.py` forwards `/api/compute`, `/api/documents` and `/api/metrics` to the server with the key. It has no database or agent logic, and all state lives server-side.
- **The agent loop is server-side**, in `src/api/services/chat.py`. `POST /v1/compute` loads the session history from Postgres, prepends `SYSTEM_PROMPT` and calls the LLM with `TOOL_SCHEMAS`. It runs tool calls for up to `MAX_TOOL_ITERATIONS` (3) iterations, then forces a final answer with no tools. The LLM is always called with `stream: true`, and the response is an SSE stream of JSON events: `delta` (text chunk), `tool` (tool being called), `status` (other progress message), then `done` or `error`. The client relays this stream as is to the browser. History is bounded by a rolling summary: `sessions.summary` replaces every message with `id <= sessions.summary_upto`, and it is merged into the system prompt. When the summary and the remaining messages exceed `CONTEXT_TOKEN_BUDGET`, `_build_context` summarizes the oldest exchanges in bounded batches and keeps the recent ones (~40% of the budget) verbatim. It emits a `status` event first. If summarizing fails, those exchanges are only left out for that turn. Raw messages are never deleted. The exchange is saved (`save_exchange`, user prompt + all streamed text) only once the answer is complete: an interrupted or failed answer is not saved. Intermediate tool messages exist only in memory.
- **Tools** are registered in the `TOOLS` dict in `src/api/services/tools.py` (async function, description and JSON-Schema parameters), and `TOOL_SCHEMAS` is derived from it. `execute_tool` never raises: errors come back as text so the model can retry. To add a tool, add an entry there.
- **RAG** lives in `src/api/services/rag.py`, for both indexing and retrieval. On upload, it checks the extension and size of uploads (text formats only, 512 KB max). It splits the text into paragraph-grouped chunks (`CHUNK_SIZE`/`CHUNK_OVERLAP` in characters), embeds them in batches (`embeddings.py`) and stores them in `documents`/`chunks`, which have an HNSW cosine index. Retrieval is `rag.search`: in hybrid mode it runs the vector search (k nearest) and a BM25 search side by side, then fuses them by Reciprocal Rank Fusion (ranks only, since cosine and BM25 scores are not comparable). BM25 is computed in SQL (`database.search_chunks_bm25`) over `chunks.tsv`, a generated `tsvector` (`french` config) with a GIN index: query terms are OR-ed, so IDF weights rare terms. Every result keeps its cosine `score`, and `bm25` if BM25 found it. The `search_documents` tool calls it and applies `RAG_MIN_SCORE`. On top of that, `stream_compute` runs `auto_search` on the raw prompt before every answer: up to 3 passages above `RAG_AUTO_MIN_SCORE` are appended to the user message for that call only (not the system prompt, to keep llama-server's prefix cache; never saved). It never raises, so an embedding outage does not block the chat.
- **Raw OpenAI-compatible proxy**: `src/api/routers/inference.py` streams `/v1/chat/completions` and `/v1/models` straight to the LLM provider, behind the Homn key, with no agent or tools.
- **Upstream HTTP**: each upstream (LLM, embeddings, client→server) has a module-level `httpx.AsyncClient` created and closed in the FastAPI `lifespan`. Upstream failures are mapped to domain exceptions (`UpstreamUnavailable`/`UpstreamTimeout` become 502/504 in `server.py`, and `InferenceError` becomes an SSE `error` event).
- **Metrics**: `/v1/metrics/all` combines psutil/NVML system stats with llama-server's Prometheus `/metrics`. The llama-server stats are empty for other providers. The chat llama-server must run with `--jinja` (tool calling) and `--metrics`.
- Shared Pydantic models live in `src/schemas.py`.

## Référence
- ~/hdd/open-webui (v0.12.3) est une référence de conception, en lecture seule.
- Quand je demande comment Open WebUI fait quelque chose, va lire son code
  (points d'entrée : backend/open_webui/models, routers, utils/middleware.py, retrieval/).
- Ne recopie jamais son code : explique le principe et adapte-le à notre architecture.
