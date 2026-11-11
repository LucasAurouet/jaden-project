import sys
from config import BIND_HOST, SERVER_PORT, CLIENT_PORT

USAGE = """Usage: python main.py <command>
  server                     inference server (GPU machine)
  client                     web interface on http://127.0.0.1:{port}
  adduser <name> [--admin]   create an account
  passwd <name>              change the password and log the account out everywhere
  deluser <name>             delete the account and its conversations
  index <file>...            index reference documents (RAG), visible to everyone
  documents                  list the indexed documents
  unindex <id>               remove a document from the index
  sync-cards [options]       update the card database from YGOPRODeck and embed it
                               --force: download again even if the version is unchanged
                               --embed-only: only embed (cards without an up-to-date vector)
                               --reembed: embed everything again (after a model change)""".format(port=CLIENT_PORT)


async def manage_users(command: str, args: list[str]) -> int:
    """Gestion des comptes, sur la base configurée dans DATABASE_URL (migrations appliquées)."""
    import asyncpg
    from getpass import getpass
    from src.api.services import auth, database

    if len(args) < 1 or args[0].startswith("-"):
        print(USAGE)
        return 1
    username = args[0]

    def ask_password() -> str:
        password = getpass(f"Password for {username}: ")
        if password != getpass("Confirm: "):
            raise ValueError("The passwords do not match.")
        return password

    await database.init_db()
    try:
        if command == "adduser":
            is_admin = "--admin" in args[1:]
            user = await database.create_user(username, await auth.hash_password(ask_password()), is_admin)
            print(f"Account {user['username']} created{' (admin)' if is_admin else ''}.")
        elif command == "passwd":
            if not await database.set_password(username, await auth.hash_password(ask_password())):
                raise LookupError(f"No account named {username}.")
            print(f"Password of {username} changed; their login sessions are revoked.")
        elif command == "deluser":
            if input(f"Delete {username} and their conversations? [y/N] ").lower() != "y":
                return 1
            if not await database.delete_user(username):
                raise LookupError(f"No account named {username}.")
            print(f"Account {username} deleted.")
    except asyncpg.UniqueViolationError:
        print(f"Error: the account {username} already exists.")
        return 1
    except (ValueError, LookupError) as e:
        print(f"Error: {e}")
        return 1
    finally:
        await database.close_db()
    return 0


async def manage_documents(command: str, args: list[str]) -> int:
    """Documents de référence du RAG, sur la base configurée dans DATABASE_URL."""
    from pathlib import Path
    from src.api.services import database, embeddings, rag
    from src.api.services.embeddings import EmbeddingError

    if command in ("index", "unindex") and not args:
        print(USAGE)
        return 1

    await database.init_db()
    await embeddings.start_client()
    status = 0
    try:
        if command == "index":
            for path in map(Path, args):
                try:
                    result = await rag.ingest(path.name, path.read_bytes())
                    print(f"{path}: indexed (id {result['id']}, {result['chunks']} passage(s)).")
                except (OSError, rag.DocumentError, EmbeddingError) as e:
                    print(f"{path}: {e}")
                    status = 1
        elif command == "documents":
            documents = await database.list_documents()
            for d in documents:
                print(f"{d['id']:>5}  {d['source']}  ({d['chunks']} passage(s), {d['created_at']:%Y-%m-%d})")
            if not documents:
                print("No indexed document.")
        elif command == "unindex":
            if not args[0].isdigit() or not await database.delete_document(int(args[0])):
                print(f"Error: no document with id {args[0]} (see python main.py documents).")
                status = 1
            else:
                print(f"Document {args[0]} removed.")
    finally:
        await embeddings.stop_client()
        await database.close_db()
    return status


async def sync_cards(args: list[str]) -> int:
    """
    Base de cartes : copie locale de l'API YGOPRODeck, puis vectorisation des
    cartes nouvelles ou modifiées. Sans fournisseur d'embeddings, les cartes
    sont tout de même mises à jour : relancer avec --embed-only plus tard.
    """
    from src.api.cards.embed import embed_cards
    from src.api.cards.sync import SyncError, sync_cards as run_sync
    from src.api.services import database, embeddings
    from src.api.services.embeddings import EmbeddingError

    await database.init_db()
    await embeddings.start_client()
    try:
        if "--embed-only" not in args:
            await run_sync(force="--force" in args)
        await embed_cards(reembed="--reembed" in args)
    except SyncError as e:
        print(f"Error: {e}")
        return 1
    except EmbeddingError as e:
        print(f"Embedding incomplete: {e}\nRun python main.py sync-cards --embed-only once the provider is available.")
        return 1
    finally:
        await embeddings.stop_client()
        await database.close_db()
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "server"

    if mode == "server":
        import uvicorn
        from src.api.server import app
        print(f"Inference server on {BIND_HOST}:{SERVER_PORT}")
        uvicorn.run(app, host=BIND_HOST, port=SERVER_PORT)

    elif mode == "client":
        import uvicorn
        from src.client.web import app
        print(f"Jaden interface on http://127.0.0.1:{CLIENT_PORT}")
        uvicorn.run(app, host="127.0.0.1", port=CLIENT_PORT)

    elif mode in ("adduser", "passwd", "deluser"):
        import asyncio
        sys.exit(asyncio.run(manage_users(mode, sys.argv[2:])))

    elif mode in ("index", "documents", "unindex"):
        import asyncio
        sys.exit(asyncio.run(manage_documents(mode, sys.argv[2:])))

    elif mode == "sync-cards":
        import asyncio
        sys.exit(asyncio.run(sync_cards(sys.argv[2:])))

    else:
        print(USAGE)
        sys.exit(1)
