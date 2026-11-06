import sys
from config import BIND_HOST, SERVER_PORT, CLIENT_PORT

USAGE = """Usage: python main.py <commande>
  server                     serveur d'inférence (machine GPU)
  client                     interface web sur http://127.0.0.1:{port}
  adduser <nom> [--admin]    crée un compte (le premier admin récupère les conversations existantes)
  passwd <nom>               change le mot de passe et déconnecte le compte partout
  deluser <nom>              supprime le compte, ses conversations et ses documents privés""".format(port=CLIENT_PORT)


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
            if input(f"Supprimer {username}, ses conversations et ses documents privés ? [o/N] ").lower() != "o":
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

    else:
        print(USAGE)
        sys.exit(1)
