import asyncio
from dotenv import load_dotenv
from src.cli import start_cli

if __name__ == "__main__":
    load_dotenv()
    
    asyncio.run(start_cli())