import asyncio
from src.client.client_app import run_query
from src.client import display


async def start_cli() -> None:
    display.print_banner()

    while True:
        try:
            user_input = input("\nMAIA App > ").strip()
            if user_input.lower() == "q":
                break
            if not user_input:
                continue

            if user_input.lower() == "/clear":
                from client_app import start_new_session
                start_new_session()
                print("Nouvelle session démarrée")
                continue
            
            wait_animation_task = asyncio.create_task(display.wait_animation())
                
            response = await run_query(user_input)
                
            wait_animation_task.cancel()
            
            try:
                await wait_animation_task
            except asyncio.CancelledError:
                pass

            display.print_response(response)

        except KeyboardInterrupt:
            break