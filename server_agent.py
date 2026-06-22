from dotenv import load_dotenv
from src.agent import start_agent

if __name__ == "__main__":
    load_dotenv()
    
    start_agent()