import asyncio
from typing import List, Dict
from src.client.services.database import save_exchange, get_chat_history, get_attachments
from src.client.services.file import FileService
from src.client.services.maia import chat_completion, InferenceError
from src.schemas import ComputeResponse

BASE_SYSTEM_PROMPT = "Tu es Maia, un assistant développeur personnel et local."
MAX_TREE_LINES = 200


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
        # sqlite3 et os.listdir sont bloquants : on les exécute dans un thread
        # pour ne pas figer la boucle asyncio (et donc les autres requêtes).
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
            answer = await chat_completion(messages)
        except InferenceError as e:
            # Rien n'est sauvegardé : l'utilisateur peut renvoyer sa question
            # sans laisser un message "user" orphelin dans l'historique.
            return ComputeResponse(session_id=session_id, content=str(e), status="error")

        await asyncio.to_thread(save_exchange, session_id, prompt, answer)
        return ComputeResponse(session_id=session_id, content=answer)
