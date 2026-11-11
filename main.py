import sys
from config import BIND_HOST, SERVER_PORT, CLIENT_PORT

USAGE = """Usage: python main.py <commande>
  server                     serveur d'inférence (machine GPU)
  client                     interface web sur http://127.0.0.1:{port}
  adduser <nom> [--admin]    crée un compte
  passwd <nom>               change le mot de passe et déconnecte le compte partout
  deluser <nom>              supprime le compte et ses conversations
  index <fichier>...         indexe des documents de référence (RAG), visibles de tous
  documents                  liste les documents indexés
  unindex <id>               retire un document de l'index""".format(port=CLIENT_PORT)


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
        password = getpass(f"Mot de passe pour {username} : ")
        if password != getpass("Confirmation : "):
            raise ValueError("Les mots de passe ne correspondent pas.")
        return password

    await database.init_db()
    try:
        if command == "adduser":
            is_admin = "--admin" in args[1:]
            user = await database.create_user(username, await auth.hash_password(ask_password()), is_admin)
            print(f"Compte {user['username']} créé{' (admin)' if is_admin else ''}.")
        elif command == "passwd":
            if not await database.set_password(username, await auth.hash_password(ask_password())):
                raise LookupError(f"Aucun compte {username}.")
            print(f"Mot de passe de {username} changé ; ses sessions de connexion sont révoquées.")
        elif command == "deluser":
            if input(f"Supprimer {username} et ses conversations ? [o/N] ").lower() != "o":
                return 1
            if not await database.delete_user(username):
                raise LookupError(f"Aucun compte {username}.")
            print(f"Compte {username} supprimé.")
    except asyncpg.UniqueViolationError:
        print(f"Erreur : le compte {username} existe déjà.")
        return 1
    except (ValueError, LookupError) as e:
        print(f"Erreur : {e}")
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
                    print(f"{path} : indexé (id {result['id']}, {result['chunks']} passage(s)).")
                except (OSError, rag.DocumentError, EmbeddingError) as e:
                    print(f"{path} : {e}")
                    status = 1
        elif command == "documents":
            documents = await database.list_documents()
            for d in documents:
                print(f"{d['id']:>5}  {d['source']}  ({d['chunks']} passage(s), {d['created_at']:%Y-%m-%d})")
            if not documents:
                print("Aucun document indexé.")
        elif command == "unindex":
            if not args[0].isdigit() or not await database.delete_document(int(args[0])):
                print(f"Erreur : aucun document d'id {args[0]} (voir python main.py documents).")
                status = 1
            else:
                print(f"Document {args[0]} retiré.")
    finally:
        await embeddings.stop_client()
        await database.close_db()
    return status


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
        print(f"Interface Homn Systems sur http://127.0.0.1:{CLIENT_PORT}")
        uvicorn.run(app, host="127.0.0.1", port=CLIENT_PORT)

    elif mode in ("adduser", "passwd", "deluser"):
        import asyncio
        sys.exit(asyncio.run(manage_users(mode, sys.argv[2:])))

    elif mode in ("index", "documents", "unindex"):
        import asyncio
        sys.exit(asyncio.run(manage_documents(mode, sys.argv[2:])))

    else:
        print(USAGE)
        sys.exit(1)
