import asyncio
import uuid
from src.client import display
from src.client.services import maia
from src.client.services.chat import ChatService
from src.client.services.database import init_db


def new_session_id() -> str:
    return f"cli-{uuid.uuid4().hex}"


async def start_cli() -> None:
    # Le CLI est un client comme l'interface web : mêmes services, même base
    # locale, seul l'affichage change.
    init_db()
    await maia.start_client()
    display.print_banner()
    session_id = new_session_id()

    try:
        while True:
            try:
                user_input = input("\nMAIA App > ").strip()
                if user_input.lower() == "q":
                    break
                if not user_input:
                    continue

                if user_input.lower() == "/clear":
                    session_id = new_session_id()
                    print("Nouvelle session démarrée")
                    continue

                wait_animation_task = asyncio.create_task(display.wait_animation())

                response = await ChatService.process_compute(session_id, user_input)

                wait_animation_task.cancel()

                try:
                    await wait_animation_task
                except asyncio.CancelledError:
                    pass

                if response.status == "success":
                    display.print_response(response.content)
                else:
                    display.print_response(f"ERREUR//: {response.content}")

            except (KeyboardInterrupt, EOFError):
                break
    finally:
        await maia.stop_client()
