import json
from typing import Any, AsyncIterator, List, Dict
from src.api.services.database import save_exchange, get_chat_history
from src.api.services.inference import stream_chat_completion, InferenceError
from src.api.services.tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = (
    "Tu es Homn, un assistant personnel. "
    "L'utilisateur peut t'avoir fourni des documents : utilise le tool search_documents "
    "dès que la question peut s'y rapporter, et cite la source des passages utilisés."
)
MAX_TOOL_ITERATIONS = 3


def _sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _merge_tool_call_deltas(calls: Dict[int, Dict[str, Any]], deltas: List[Dict[str, Any]]):
    """
    Reconstitue les tool_calls à partir des morceaux streamés : l'id et le nom
    arrivent une fois, les arguments JSON sont découpés en fragments.
    """
    for position, delta in enumerate(deltas):
        call = calls.setdefault(
            delta.get("index", position),
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if delta.get("id"):
            call["id"] = delta["id"]
        function = delta.get("function") or {}
        if function.get("name"):
            call["function"]["name"] = function["name"]
        arguments = function.get("arguments")
        # Certains fournisseurs envoient les arguments déjà décodés, d'un bloc.
        if isinstance(arguments, str):
            call["function"]["arguments"] += arguments
        elif arguments:
            call["function"]["arguments"] = json.dumps(arguments)


class ChatService:

    @staticmethod
    async def stream_compute(session_id: str, prompt: str) -> AsyncIterator[str]:
        """
        Fait tourner l'agent et renvoie un flux SSE d'événements JSON :
        delta (morceau de réponse), tool (appel d'un tool), done ou error.
        L'échange n'est enregistré qu'une fois la réponse complète.
        """
        history = await get_chat_history(session_id)

        # L'historique en base ne contient que des tours user/assistant :
        # le message système est ajouté à chaque appel.
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + history
            + [{"role": "user", "content": prompt}]
        )

        answer = ""
        try:
            async for event in ChatService._run_agent_loop(messages):
                if event["type"] == "delta":
                    answer += event["content"]
                yield _sse(event)
        except InferenceError as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        await save_exchange(session_id, prompt, answer)
        yield _sse({"type": "done"})

    @staticmethod
    async def _run_agent_loop(messages: List[Dict[str, Any]]) -> AsyncIterator[Dict[str, Any]]:
        """
        Appelle le modèle tant qu'il demande des tools. Les messages tool
        intermédiaires ne vivent qu'en mémoire : seule la réponse est persistée.
        """
        for iteration in range(MAX_TOOL_ITERATIONS + 1):
            # Limite atteinte : le dernier appel se fait sans tools pour forcer une réponse finale.
            tools = TOOL_SCHEMAS if iteration < MAX_TOOL_ITERATIONS else None

            content = ""
            calls: Dict[int, Dict[str, Any]] = {}
            async for delta in stream_chat_completion(messages, tools=tools):
                if delta.get("content"):
                    content += delta["content"]
                    yield {"type": "delta", "content": delta["content"]}
                if delta.get("tool_calls"):
                    _merge_tool_call_deltas(calls, delta["tool_calls"])

            if not calls:
                return

            tool_calls = [calls[index] for index in sorted(calls)]
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for call in tool_calls:
                yield {"type": "tool", "name": call["function"]["name"]}
                result = await execute_tool(call["function"]["name"], call["function"]["arguments"])
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

            # Sépare le texte annonçant l'appel de la suite de la réponse.
            if content:
                yield {"type": "delta", "content": "\n\n"}
