import asyncio
from dotenv import load_dotenv
from src.cli import start_cli

if __name__ == "__main__":
    # On charge l'environnement (Liste des IP des nœuds, etc.)
    load_dotenv()
    
    # On lance la boucle asynchrone de l'interface terminal
    asyncio.run(start_cli())