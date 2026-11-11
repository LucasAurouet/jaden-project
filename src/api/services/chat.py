import json
from typing import Any, AsyncIterator, Iterator, List, Dict
from config import CONTEXT_TOKEN_BUDGET, RAG_AUTO_SEARCH
from src.api.services.database import save_exchange, get_chat_context, save_summary, SessionOwnershipError
from src.api.services.inference import stream_chat_completion, complete_chat, InferenceError
from src.api.services.rag import auto_search, format_passages
from src.api.services.tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = (
    "Tu es Homn, un assistant personnel. "
    "Des documents de référence sont indexés : utilise le tool search_documents "
    "dès que la question peut s'y rapporter, et cite la source des passages utilisés. "
    "Des passages trouvés automatiquement peuvent être joints au message de l'utilisateur : "
    "ignore-les s'ils sont hors sujet, et utilise search_documents s'ils ne suffisent pas."
)
MAX_TOOL_ITERATIONS = 3

# Part du budget gardée en messages bruts lors d'un résumé : le reste est résumé,
# ce qui laisse de la marge avant le prochain.
CONTEXT_KEEP_RATIO = 0.4
SUMMARY_MAX_TOKENS = 1024
SUMMARY_PROMPT = """Résume la conversation ci-dessous : ce résumé remplacera ces échanges dans la mémoire de l'assistant.

Consignes :
- Conserve les faits donnés par l'utilisateur, ses préférences, ses contraintes et les décisions prises.
- Conserve les informations importantes des réponses, avec les sources de documents citées.
- Conserve les questions en suspens et la tâche en cours.
- Sois factuel et précis, n'invente rien.
- Reste concis, mais assez complet pour poursuivre la conversation sans les échanges d'origine.
- Réponds uniquement par le résumé, en français.

### Résumé précédent :
{previous}

### Échanges à résumer :
{exchanges}"""


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


def _estimate_tokens(text: str | None) -> int:
    """Estimation grossière : environ 4 caractères par token."""
    return len(text or "") // 4


def _estimate_messages(messages: List[Dict[str, Any]]) -> int:
    return sum(4 + _estimate_tokens(message["content"]) for message in messages)


def _group_exchanges(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Découpe l'historique en échanges, chacun commençant par un message user."""
    exchanges: List[List[Dict[str, Any]]] = []
    for message in messages:
        if message["role"] == "user" or not exchanges:
            exchanges.append([])
        exchanges[-1].append(message)
    return exchanges


def _batches(exchanges: List[List[Dict[str, Any]]], limit: int) -> Iterator[List[Dict[str, Any]]]:
    """Regroupe des échanges consécutifs en lots d'environ limit tokens au plus."""
    batch: List[Dict[str, Any]] = []
    size = 0
    for exchange in exchanges:
        cost = _estimate_messages(exchange)
        if batch and size + cost > limit:
            yield batch
            batch, size = [], 0
        batch.extend(exchange)
        size += cost
    if batch:
        yield batch


async def _summarize(previous: str | None, messages: List[Dict[str, Any]]) -> str:
    # Un message géant est tronqué pour que l'appel de résumé tienne dans le contexte.
    max_chars = CONTEXT_TOKEN_BUDGET
    labels = {"user": "Utilisateur", "assistant": "Assistant"}
    exchanges = "\n\n".join(
        f"{labels.get(message['role'], message['role'])} : {message['content'][:max_chars]}"
        for message in messages
    )
    prompt = SUMMARY_PROMPT.format(previous=previous or "(aucun)", exchanges=exchanges)
    summary = (await complete_chat([{"role": "user", "content": prompt}], max_tokens=SUMMARY_MAX_TOKENS)).strip()
    if not summary:
        raise InferenceError("Le modèle a renvoyé un résumé vide.")
    return summary


class ChatService:

    @staticmethod
    async def stream_compute(user_id: int, session_id: str, prompt: str) -> AsyncIterator[str]:
        """
        Fait tourner l'agent et renvoie un flux SSE d'événements JSON :
        delta (morceau de réponse), tool (appel d'un tool), done ou error.
        L'échange n'est enregistré qu'une fois la réponse complète.
        """
        summary, history = None, []
        async for event in ChatService._build_context(user_id, session_id):
            if event["type"] == "context":
                summary, history = event["summary"], event["history"]
            else:
                yield _sse(event)

        # Les passages sont joints au message plutôt qu'au prompt système : le début
        # du prompt reste identique d'un tour à l'autre (cache de llama-server).
        # Ils ne sont pas enregistrés : seul le prompt brut l'est.
        question = prompt
        if RAG_AUTO_SEARCH:
            passages = await auto_search(prompt)
            if passages:
                yield _sse({"type": "status", "message": f"{len(passages)} passage(s) trouvé(s) dans les documents"})
                question += (
                    "\n\n---\nPassages des documents trouvés automatiquement "
                    f"(peut-être hors sujet) :\n\n{format_passages(passages)}"
                )

        # L'historique en base ne contient que des tours user/assistant :
        # le message système est ajouté à chaque appel. Le résumé y est fusionné,
        # car certains templates refusent un second message système.
        system = SYSTEM_PROMPT
        if summary:
            system += f"\n\nRésumé des échanges précédents :\n{summary}"
        messages = (
            [{"role": "system", "content": system}]
            + [{"role": message["role"], "content": message["content"]} for message in history]
            + [{"role": "user", "content": question}]
        )

        answer = ""
        try:
            async for event in ChatService._run_agent_loop(messages, user_id):
                if event["type"] == "delta":
                    answer += event["content"]
                yield _sse(event)
        except InferenceError as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        try:
            await save_exchange(user_id, session_id, prompt, answer)
        except SessionOwnershipError:
            yield _sse({"type": "error", "message": "Conversation introuvable : la réponse n'a pas été enregistrée."})
            return
        yield _sse({"type": "done"})

    @staticmethod
    async def _build_context(user_id: int, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Charge le résumé et l'historique de la session. Si l'ensemble dépasse
        CONTEXT_TOKEN_BUDGET, les anciens échanges sont résumés et le résumé
        enregistré en base. Termine par un événement interne "context".
        """
        summary, history = await get_chat_context(session_id, user_id)

        if _estimate_tokens(summary) + _estimate_messages(history) > CONTEXT_TOKEN_BUDGET:
            exchanges = _group_exchanges(history)
            # On garde au moins le dernier échange, puis les précédents tant qu'ils tiennent.
            keep = len(exchanges) - 1
            size = _estimate_messages(exchanges[-1])
            while keep > 0 and size + _estimate_messages(exchanges[keep - 1]) <= CONTEXT_KEEP_RATIO * CONTEXT_TOKEN_BUDGET:
                keep -= 1
                size += _estimate_messages(exchanges[keep])

            if keep > 0:
                yield {"type": "status", "message": "Résumé de l'historique…"}
                history = [message for exchange in exchanges[keep:] for message in exchange]
                try:
                    # Par lots bornés : une session très longue se résorbe en plusieurs passes.
                    for batch in _batches(exchanges[:keep], CONTEXT_TOKEN_BUDGET // 2):
                        summary = await _summarize(summary, batch)
                        await save_summary(session_id, summary, batch[-1]["id"])
                except InferenceError:
                    # Repli : les échanges non résumés sont simplement omis pour ce tour,
                    # le résumé reprendra au prochain.
                    pass

        yield {"type": "context", "summary": summary, "history": history}

    @staticmethod
    async def _run_agent_loop(messages: List[Dict[str, Any]], user_id: int) -> AsyncIterator[Dict[str, Any]]:
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
                result = await execute_tool(call["function"]["name"], call["function"]["arguments"], user_id)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

            # Sépare le texte annonçant l'appel de la suite de la réponse.
            if content:
                yield {"type": "delta", "content": "\n\n"}
