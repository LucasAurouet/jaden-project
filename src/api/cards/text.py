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
