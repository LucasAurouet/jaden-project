import asyncio
from typing import Any, List, Dict
from src.client.services.database import save_exchange, get_chat_history, get_attachments
from src.client.services.file import FileService
from src.client.services.homn import chat_completion, InferenceError
from src.client.services.tools import TOOL_SCHEMAS, execute_tool
from src.schemas import ComputeResponse

BASE_SYSTEM_PROMPT = (
    "Tu es Homn, un assistant développeur personnel et local. "
    "Tu peux consulter le workspace grâce aux tools list_dir, read_file et search : "
    "utilise-les plutôt que de deviner le contenu d'un fichier."
)
MAX_TREE_LINES = 200
MAX_TOOL_ITERATIONS = 3


def build_system_prompt(attachments: List[Dict[str, str]], tree: str) -> str:
    """
    Le contexte (workspace, fichiers) est reconstruit à chaque appel et placé
    dans l'unique message système, en tête de conversation. L'historique en
    base ne contient ainsi que des tours user/assistant, sans doublons.
    """
    parts = [BASE_SYSTEM_PROMPT]

    tree_lines = tree.splitlines()
    if len(tree_lines) > MAX_TREE_LINES:
        tree_lines = tree_lines[:MAX_TREE_LINES] + ["... (arborescence tronquée)"]
    parts.append("Arborescence du workspace :\n" + "\n".join(tree_lines))

    for att in attachments:
        parts.append(
            f"--- DÉBUT DU FICHIER : {att['filename']} ---\n"
            f"{att['content']}\n"
            f"--- FIN DU FICHIER : {att['filename']} ---"
        )

    return "\n\n".join(parts)


class ChatService:

    @staticmethod
    async def process_compute(session_id: str, prompt: str) -> ComputeResponse:
        history, attachments, workspace = await asyncio.gather(
            asyncio.to_thread(get_chat_history, session_id),
            asyncio.to_thread(get_attachments, session_id),
            asyncio.to_thread(FileService.list_workspace_files),
        )

        messages = (
            [{"role": "system", "content": build_system_prompt(attachments, workspace["tree"])}]
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
