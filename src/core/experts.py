"""
Registre des experts MAIA.
Responsabilité unique : mapper un type d'expert vers son system prompt.
"""

EXPERT_REGISTRY: dict[str, str] = {
    "code":    "Tu es un ingénieur logiciel senior. Donne du code optimisé.",
    "maths":   "Tu es un mathématicien. Résous le problème étape par étape.",
    "writing": "Tu es un rédacteur professionnel. Rédige de manière claire.",
}

DEFAULT_PROMPT = "Tu es un assistant généraliste."

# Cycle déterministe : assigne un expert à chaque peer par index
EXPERT_ROLES: list[str] = list(EXPERT_REGISTRY.keys())


def get_system_prompt(expert_type: str) -> str:
    return EXPERT_REGISTRY.get(expert_type, DEFAULT_PROMPT)


def assign_expert(peer_index: int) -> str:
    """Retourne le type d'expert associé à l'index du peer."""
    return EXPERT_ROLES[peer_index % len(EXPERT_ROLES)]