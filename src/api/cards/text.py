import unicodedata


def normalize_name(name: str) -> str:
    """
    Forme de comparaison d'un nom de carte : minuscules, sans accents ni
    ponctuation, espaces réduits. Utilisée à la synchronisation (cards.name_key_*)
    et à la recherche, pour que « blue eyes white dragon » corresponde exactement
    à « Blue-Eyes White Dragon » et « heros elementaire neos » à « Néos, HÉROS Élémentaire ».
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in stripped.casefold()).split())


# Mots courants propres à chaque langue, pour deviner celle d'une requête.
_ENGLISH_WORDS = {
    "the", "a", "an", "your", "you", "from", "to", "of", "and", "or", "all", "this", "that", "with",
    "in", "on", "when", "if", "can", "card", "cards", "which", "what", "my", "is", "are",
}
_FRENCH_WORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "votre", "vos", "depuis", "et", "ou", "tous",
    "toutes", "ce", "cette", "avec", "dans", "sur", "quand", "si", "carte", "cartes", "quelles",
    "quel", "quels", "mon", "est", "sont", "qui", "au", "aux",
}


def guess_language(text: str) -> str | None:
    """
    "english" ou "french" (noms des configurations plein texte de Postgres)
    d'après les mots courants de text ; None si on ne peut pas trancher.
    """
    words = normalize_name(text).split()
    english = sum(word in _ENGLISH_WORDS for word in words)
    french = sum(word in _FRENCH_WORDS for word in words) + sum(c in "éèêàùçô" for c in text.lower())
    if english > french:
        return "english"
    if french > english:
        return "french"
    return None
