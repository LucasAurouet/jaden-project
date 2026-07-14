import asyncio
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
            
            wait_animation_task = asyncio.create_task(display.wait_animation())
                
            response = await run_query(prompt)
                
            wait_animation_task.cancel()
            
            try:
                await wait_animation_task
            except asyncio.CancelledError:
                pass

            display.print_response(response)

        except KeyboardInterrupt:
            break