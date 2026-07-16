from typing import Tuple
from src.api.services.database import save_message, get_chat_history
from src.api.services.inference import run_inference

class ChatService:

    
    @staticmethod
    async def process_compute(session_id: str, prompt: str) -> Tuple[str, str, str]:

        save_message(session_id, "user", prompt)
        history = get_chat_history(session_id)
        
        messages = [{"role": "system", "content": "Tu es Maia, un assistant développeur personnel et local."}] + history

        url = "http://127.0.0.1:8080/v1/chat/completions"
        
        try:
            assistant_response = await run_inference(messages, url)
        except Exception as e:
            assistant_response = f"[Erreur] Impossible de joindre l'IA locale : {str(e)}"
        
        if not assistant_response.startswith("[Erreur]"):
            save_message(session_id, "assistant", assistant_response)
            status_code = "success"
        else:
            status_code = "error"

        return ComputeResponse(
            session_id=str(session_id),
            content=str(assistant_response),
            status=str(status_code)
        )
