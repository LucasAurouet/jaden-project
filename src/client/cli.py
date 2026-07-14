from src.client.client_app import run_query
from src.client import display


async def start_cli() -> None:
    display.print_banner()

    while True:
        try:
            prompt = input("\nMAIA App > ").strip()
            if prompt.lower() == "q":
                break
            if not prompt:
                continue
            
            response = await run_query(prompt)
            display.print_response(response)

        except KeyboardInterrupt:
            break