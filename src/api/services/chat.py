import asyncio
from typing import Any, List, Dict
from src.api.services.database import save_exchange, get_chat_history
from src.api.services.inference import chat_completion, InferenceError
from src.api.services.tools import TOOL_SCHEMAS, execute_tool
from src.schemas import ComputeResponse

SYSTEM_PROMPT = "Tu es Homn, un assistant développeur personnel et local."
MAX_TOOL_ITERATIONS = 3


class ChatService:

    @staticmethod
    async def process_compute(session_id: str, prompt: str) -> ComputeResponse:
        history = await asyncio.to_thread(get_chat_history, session_id)

        # L'historique en base ne contient que des tours user/assistant :
        # le message système est ajouté à chaque appel.
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history
            + [{"role": "user", "content": prompt}]
        )

        try:
            answer = await ChatService._run_agent_loop(messages)
        except InferenceError as e:
            return ComputeResponse(session_id=session_id, content=str(e), status="error")

        await asyncio.to_thread(save_exchange, session_id, prompt, answer)
        return ComputeResponse(session_id=session_id, content=answer)

    @staticmethod
    async def _run_agent_loop(messages: List[Dict[str, Any]]) -> str:
        """
        Appelle le modèle tant qu'il demande des tools. Les messages tool
        intermédiaires ne vivent qu'en mémoire : seule la réponse finale est
        persistée.
        """
        for _ in range(MAX_TOOL_ITERATIONS):
            message = await chat_completion(messages, tools=TOOL_SCHEMAS)
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return message.get("content") or ""

            messages.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            })
            for call in tool_calls:
                result = await execute_tool(call["function"]["name"], call["function"].get("arguments"))
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        # Limite atteinte : on force une réponse finale sans tools.
        message = await chat_completion(messages)
        return message.get("content") or ""
