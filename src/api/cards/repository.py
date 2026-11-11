"""
Requêtes sur la base de cartes : recherche par nom (trigrammes), par id
d'artwork (fichiers .ydk) et recherche hybride filtrée sur les effets.
"""
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List

import asyncpg

from config import EMBEDDING_QUERY_PREFIX
from src.api.cards.text import normalize_name
from src.api.services import database
from src.api.services.embeddings import embed, EmbeddingError

# Colonnes renvoyées pour une carte (le reste est dans raw).
CARD_FIELDS = """
    c.id, c.name, c.description, c.type, c.frame_type, c.typeline, c.race,
    c.attribute, c.archetype, c.level, c.atk, c.def, c.scale, c.link_rating, c.link_markers,
    c.formats, c.md_rarity
"""

MASTER_DUEL = "Master Duel"

# Recherche hybride : candidats demandés à chaque recherche avant fusion, et
# constante de la Reciprocal Rank Fusion (60 d'usage).
MIN_CANDIDATES = 30
RRF_K = 60

# Types de carte acceptés par le filtre card_type, et leur condition SQL.
_FRAME_PREFIXES = ("fusion", "synchro", "xyz", "link", "ritual")
_TYPELINE_KINDS = ("normal", "effect", "tuner", "flip", "gemini", "spirit", "toon", "union")
CARD_TYPES = ("monster", "spell", "trap", "pendulum") + _FRAME_PREFIXES + _TYPELINE_KINDS


def _rows(rows: List[asyncpg.Record]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


# ─── Par nom ────────────────────────────────────────────────────────────────

async def find_by_name(name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Cartes dont le nom ressemble le plus à name : nom exact d'abord, puis par
    similarité de trigrammes. Tolère la casse, la ponctuation, les fautes de
    frappe et l'ordre des mots.
    """
    key = normalize_name(name)
    if not key:
        return []
    rows = await database.get_pool().fetch(f"""
        SELECT {CARD_FIELDS}, c.name_key = $1 AS exact, similarity($1, c.name_key) AS score
        FROM cards c
        WHERE c.name_key % $1 OR c.name_key LIKE '%' || $1 || '%'
        ORDER BY exact DESC, score DESC, length(c.name)
        LIMIT $2
    """, key, limit)
    return _rows(rows)


async def get_by_ids(ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Cartes désignées par un id de carte ou d'artwork (fichiers .ydk), par id demandé."""
    rows = await database.get_pool().fetch(f"""
        SELECT a.id AS requested_id, {CARD_FIELDS}
        FROM card_artworks a JOIN cards c ON c.id = a.card_id
        WHERE a.id = ANY($1::bigint[])
    """, ids)
    return {row["requested_id"]: {k: v for k, v in dict(row).items() if k != "requested_id"} for row in rows}


async def get_archetype(archetype: str, master_duel_only: bool = True) -> List[Dict[str, Any]]:
    """Cartes de l'archétype (nom exact, sans tenir compte de la casse), par type puis par nom."""
    rows = await database.get_pool().fetch(f"""
        SELECT {CARD_FIELDS} FROM cards c
        WHERE lower(c.archetype) = lower($1) AND (NOT $2 OR c.formats @> ARRAY[$3])
        ORDER BY c.frame_type IN ('spell', 'trap'), c.frame_type, c.name
    """, archetype, master_duel_only, MASTER_DUEL)
    return _rows(rows)


async def find_archetypes(name: str, limit: int = 5) -> List[str]:
    """Noms d'archétypes proches de name, pour corriger une demande approximative."""
    rows = await database.get_pool().fetch("""
        SELECT archetype FROM (SELECT DISTINCT archetype FROM cards WHERE archetype IS NOT NULL) a
        WHERE lower(archetype) % lower($1) OR lower(archetype) LIKE '%' || lower($1) || '%'
        ORDER BY similarity(lower(archetype), lower($1)) DESC
        LIMIT $2
    """, name, limit)
    return [row["archetype"] for row in rows]


# ─── Recherche filtrée ──────────────────────────────────────────────────────

@dataclass
class CardFilters:
    """Critères structurés : appliqués en SQL avant tout classement par pertinence."""
    card_type: str | None = None      # voir CARD_TYPES
    attribute: str | None = None      # LIGHT, DARK...
    race: str | None = None           # type de monstre (Warrior...) ou de Magie/Piège (Quick-Play...)
    archetype: str | None = None
    level_min: int | None = None      # niveau, rang ou classe de Lien
    level_max: int | None = None
    atk_min: int | None = None
    atk_max: int | None = None
    def_min: int | None = None
    def_max: int | None = None
    master_duel_only: bool = True

    def where(self, params: List[Any]) -> str:
        """Clause WHERE ; ajoute ses valeurs à params (placeholders $n à la suite)."""
        conditions = ["c.formats @> ARRAY['Master Duel']"] if self.master_duel_only else []

        def param(value: Any) -> str:
            params.append(value)
            return f"${len(params)}"

        if self.card_type:
            kind = self.card_type.lower()
            if kind not in CARD_TYPES:
                raise ValueError(f"card_type inconnu '{self.card_type}' (valeurs : {', '.join(CARD_TYPES)})")
            if kind == "monster":
                conditions.append("c.frame_type NOT IN ('spell', 'trap')")
            elif kind in ("spell", "trap"):
                conditions.append(f"c.frame_type = {param(kind)}")
            elif kind == "pendulum":
                conditions.append("c.frame_type LIKE '%pendulum'")
            elif kind in _FRAME_PREFIXES:
                conditions.append(f"c.frame_type LIKE {param(kind)} || '%'")
            else:
                conditions.append(f"EXISTS (SELECT 1 FROM unnest(c.typeline) t WHERE lower(t) = {param(kind)})")
        if self.attribute:
            conditions.append(f"lower(c.attribute) = lower({param(self.attribute)})")
        if self.race:
            conditions.append(f"lower(c.race) = lower({param(self.race)})")
        if self.archetype:
            conditions.append(f"lower(c.archetype) = lower({param(self.archetype)})")
        # Un monstre Lien n'a ni niveau ni rang : sa classe de Lien en tient lieu.
        level = "coalesce(c.link_rating, c.level)"
        for column, low, high in (
            (level, self.level_min, self.level_max),
            ("c.atk", self.atk_min, self.atk_max),
            ("c.def", self.def_min, self.def_max),
        ):
            if low is not None:
                conditions.append(f"{column} >= {param(int(low))}")
            if high is not None:
                # -1 code une valeur « ? » : elle ne passe pas un maximum.
                conditions.append(f"{column} BETWEEN 0 AND {param(int(high))}")
        return " AND ".join(conditions) or "true"


def _fuse(*rankings: List[int]) -> List[int]:
    """Reciprocal Rank Fusion des classements d'ids (seuls les rangs comptent)."""
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, card_id in enumerate(ranking, 1):
            scores[card_id] = scores.get(card_id, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)


async def _vector_ranking(embedding: List[float], where: str, params: List[Any], n: int) -> List[int]:
    rows = await database.get_pool().fetch(f"""
        SELECT c.id FROM cards c
        WHERE {where} AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> ${len(params) + 1}
        LIMIT ${len(params) + 2}
    """, *params, embedding, n)
    return [row["id"] for row in rows]


# Paramètres usuels de BM25 : saturation de la fréquence d'un terme (k1) et
# normalisation par la longueur du texte (b).
BM25_K1 = 1.2
BM25_B = 0.75


def _bm25_sql(where: str, q: str) -> str:
    """
    Score BM25 de chaque carte filtrée pour la requête ${q}, sur cards.search.
    Il suffit qu'une carte contienne un des termes : l'IDF donne leur poids aux
    termes rares (« Tuner » pèse plus que « Deck » ou « hand », présents presque
    partout). Les statistiques portent sur toute la base, pas seulement sur les
    cartes filtrées.
    """
    terms = f"tsvector_to_array(to_tsvector('english', ${q}))"
    return f"""
        SELECT tf.id, sum(
            ln(1 + (stats.total - df.n + 0.5) / (df.n + 0.5))
            * tf.freq * ({BM25_K1} + 1) / (tf.freq + {BM25_K1} * (1 - {BM25_B} + {BM25_B} * tf.len / stats.avg_len))
        ) AS bm25
        FROM (
            SELECT c.id, t.lexeme, cardinality(t.positions) AS freq, length(c.search) AS len
            FROM cards c, unnest(c.search) t
            WHERE {where}
              AND c.search @@ replace(plainto_tsquery('english', ${q})::text, ' & ', ' | ')::tsquery
              AND t.lexeme = ANY({terms})
        ) tf
        JOIN (
            SELECT t.lexeme, count(*) AS n FROM cards c, unnest(c.search) t
            WHERE t.lexeme = ANY({terms})
            GROUP BY t.lexeme
        ) df USING (lexeme)
        CROSS JOIN (SELECT count(*) AS total, avg(length(search)) AS avg_len FROM cards) stats
        GROUP BY tf.id
    """


async def _text_ranking(query: str, where: str, params: List[Any], n: int) -> List[int]:
    """Recherche plein texte (BM25) sur les noms et les effets."""
    # Une requête faite uniquement de mots vides donne un tsquery vide : rien à chercher.
    if not await database.get_pool().fetchval("SELECT numnode(plainto_tsquery('english', $1))", query):
        return []
    q = len(params) + 1
    rows = await database.get_pool().fetch(f"""
        SELECT id FROM ({_bm25_sql(where, str(q))}) scores
        ORDER BY bm25 DESC
        LIMIT ${q + 1}
    """, *params, query, n)
    return [row["id"] for row in rows]


async def search_cards(query: str | None, filters: CardFilters, limit: int = 10) -> Dict[str, Any]:
    """
    Cartes qui respectent les filtres, classées par pertinence pour query (en
    langage naturel, en anglais) : fusion de la recherche vectorielle
    et plein texte. Sans query, par nom. Si le fournisseur d'embeddings est
    indisponible, seule la recherche plein texte classe les cartes.
    Renvoie {"cards": [...], "total": nombre de cartes qui respectent les filtres, "mode": ...}.
    """
    params: List[Any] = []
    where = filters.where(params)
    pool = database.get_pool()
    total = await pool.fetchval(f"SELECT count(*) FROM cards c WHERE {where}", *params)

    if not query or not query.strip():
        rows = await pool.fetch(
            f"SELECT {CARD_FIELDS} FROM cards c WHERE {where} ORDER BY c.name LIMIT ${len(params) + 1}",
            *params, limit,
        )
        return {"cards": _rows(rows), "total": total, "mode": "filters"}

    n = max(3 * limit, MIN_CANDIDATES)
    mode = "hybrid"
    try:
        [embedding] = await embed([EMBEDDING_QUERY_PREFIX + query])
        vector, text = await asyncio.gather(
            _vector_ranking(embedding, where, params, n),
            _text_ranking(query, where, params, n),
        )
        ranked = _fuse(vector, text)
    except EmbeddingError:
        ranked = await _text_ranking(query, where, params, n)
        mode = "text"

    ids = ranked[:limit]
    rows = await pool.fetch(f"SELECT {CARD_FIELDS} FROM cards c WHERE c.id = ANY($1::bigint[])", ids)
    by_id = {row["id"]: dict(row) for row in rows}
    return {"cards": [by_id[i] for i in ids if i in by_id], "total": total, "mode": mode}
