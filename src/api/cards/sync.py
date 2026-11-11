"""
Synchronisation de la base de cartes depuis l'API YGOPRODeck (python main.py sync-cards).

Règles de l'API : 20 requêtes/s au plus (au-delà, blocage d'une heure) et
données stockées localement. Une synchronisation complète ne fait que trois
requêtes : la version de la base, puis toutes les cartes en anglais et en
français. Les images ne sont pas téléchargées ici.
"""
import asyncio
import json
from typing import Any, Callable, Dict, List

import httpx

from src.api.cards.text import normalize_name
from src.api.services import database

API_URL = "https://db.ygoprodeck.com/api/v7"
USER_AGENT = "Jaden/0.1 (card sync)"
# Chaque liste complète fait ~25 Mo.
TIMEOUT = httpx.Timeout(180.0, connect=10.0)
# Marge entre deux requêtes, très en dessous de la limite.
REQUEST_PAUSE = 1.0

# Cartes Skill (Duel Links / Speed Duel) et jetons : pas des cartes jouables d'un deck.
EXCLUDED_FRAME_TYPES = {"skill", "token"}

VERSION_KEY = "ygoprodeck_db_version"


class SyncError(Exception):
    """L'API YGOPRODeck est injoignable ou a renvoyé des données inattendues."""


async def _get_json(client: httpx.AsyncClient, path: str, params: Dict[str, str] | None = None) -> Any:
    try:
        response = await client.get(path, params=params)
    except httpx.HTTPError as e:
        raise SyncError(f"API YGOPRODeck injoignable ({e.__class__.__name__}).") from e
    if response.status_code != 200:
        raise SyncError(f"Erreur HTTP {response.status_code} de l'API YGOPRODeck sur {path} : {response.text[:200]}")
    try:
        return response.json()
    except ValueError as e:
        raise SyncError(f"Réponse de {path} illisible (JSON invalide).") from e


async def _fetch_cards(client: httpx.AsyncClient, language: str | None) -> List[Dict[str, Any]]:
    params = {"misc": "yes"}
    if language:
        params["language"] = language
    data = await _get_json(client, "/cardinfo.php", params)
    try:
        return data["data"]
    except (KeyError, TypeError) as e:
        raise SyncError("Réponse de cardinfo.php inattendue (pas de champ data).") from e


def _translations(cards_en: List[Dict[str, Any]], cards_fr: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Traduction française de chaque carte anglaise, par id de carte. Pour une
    carte à plusieurs artworks, les deux langues ne prennent pas toujours le même
    id principal : on cherche aussi parmi les ids d'artwork, puis par nom anglais.
    """
    by_id = {card["id"]: card for card in cards_fr}
    by_name = {card["name_en"]: card for card in cards_fr if card.get("name_en")}
    translations = {}
    for card in cards_en:
        ids = [card["id"]] + [image["id"] for image in card.get("card_images") or []]
        fr = next((by_id[i] for i in ids if i in by_id), None) or by_name.get(card["name"])
        if fr:
            translations[card["id"]] = fr
    return translations


def _card_row(card: Dict[str, Any], fr: Dict[str, Any] | None) -> tuple:
    """Ligne de la table cards, à partir de la carte anglaise et de sa traduction."""
    misc = (card.get("misc_info") or [{}])[0]
    name_fr = fr.get("name") if fr else None
    desc_fr = fr.get("desc") if fr else None
    # Les prix changent sans cesse et ne servent à rien ici.
    raw = {k: v for k, v in card.items() if k != "card_prices"}
    return (
        card["id"],
        misc.get("konami_id"),
        card["name"],
        name_fr,
        normalize_name(card["name"]),
        normalize_name(name_fr) if name_fr else None,
        card.get("desc") or "",
        desc_fr,
        card["type"],
        card["frameType"],
        card.get("typeline") or [],
        card.get("race"),
        card.get("attribute"),
        card.get("archetype"),
        card.get("level"),
        card.get("atk"),
        card.get("def"),
        card.get("scale"),
        card.get("linkval"),
        card.get("linkmarkers"),
        misc.get("formats") or [],
        misc.get("md_rarity"),
        json.dumps(raw, ensure_ascii=False),
    )


CARD_COLUMNS = (
    "id, konami_id, name_en, name_fr, name_key_en, name_key_fr, desc_en, desc_fr, type, frame_type, typeline, "
    "race, attribute, archetype, level, atk, def, scale, link_rating, link_markers, formats, md_rarity, raw"
)
UPSERT_CARD = f"""
    INSERT INTO cards ({CARD_COLUMNS}, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23::jsonb, now())
    ON CONFLICT (id) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in CARD_COLUMNS.split(", ") if c != "id")},
    updated_at = now()
"""


async def sync_cards(force: bool = False, log: Callable[[str], None] = print) -> Dict[str, Any]:
    """
    Met la base de cartes à jour si la version de YGOPRODeck a changé (ou si
    force). Tout est écrit dans une seule transaction : une synchronisation
    interrompue laisse la base précédente intacte.
    """
    pool = database.get_pool()
    async with httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            [remote] = await _get_json(client, "/checkDBVer.php")
            version = str(remote["database_version"])
        except (ValueError, KeyError, TypeError) as e:
            raise SyncError("Réponse de checkDBVer.php inattendue.") from e

        local = await pool.fetchval("SELECT value FROM sync_state WHERE key = $1", VERSION_KEY)
        if local == version and not force:
            log(f"Base de cartes déjà à jour (version YGOPRODeck {version}).")
            return {"updated": False, "version": version}

        log(f"Téléchargement des cartes (version YGOPRODeck {version}, locale {local or 'aucune'})…")
        await asyncio.sleep(REQUEST_PAUSE)
        cards_en = await _fetch_cards(client, None)
        log(f"  {len(cards_en)} cartes en anglais")
        await asyncio.sleep(REQUEST_PAUSE)
        cards_fr = await _fetch_cards(client, "fr")
        log(f"  {len(cards_fr)} cartes en français")

    cards = [c for c in cards_en if c.get("frameType") not in EXCLUDED_FRAME_TYPES]
    try:
        translations = _translations(cards, cards_fr)
        rows = [_card_row(card, translations.get(card["id"])) for card in cards]
    except (KeyError, TypeError) as e:
        raise SyncError(f"Carte au format inattendu ({e}).") from e
    # Un id d'artwork déjà vu est ignoré : il ne doit désigner qu'une carte.
    artworks: Dict[int, tuple] = {}
    for card in cards:
        for position, image in enumerate(card.get("card_images") or []):
            artworks.setdefault(image["id"], (image["id"], card["id"], position))

    ids = [row[0] for row in rows]
    async with pool.acquire() as conn, conn.transaction():
        await conn.executemany(UPSERT_CARD, rows)
        removed = await conn.fetchval(
            "WITH gone AS (DELETE FROM cards WHERE id <> ALL($1::bigint[]) RETURNING 1) SELECT count(*) FROM gone", ids
        )
        await conn.execute("DELETE FROM card_artworks")
        await conn.executemany(
            "INSERT INTO card_artworks (id, card_id, position) VALUES ($1, $2, $3)", list(artworks.values())
        )
        await conn.execute(
            "INSERT INTO sync_state (key, value) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            VERSION_KEY, version,
        )

    translated = sum(1 for row in rows if row[3])
    log(
        f"{len(rows)} cartes enregistrées ({translated} traduites en français, "
        f"{len(cards_en) - len(cards)} cartes Skill et jetons ignorés, {removed} retirées), "
        f"{len(artworks)} artworks."
    )
    return {"updated": True, "version": version, "cards": len(rows), "removed": removed}
