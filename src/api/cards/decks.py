"""
Deck d'une conversation : lecture du fichier .ydk importé, résolution des
cartes dans la base locale et texte injecté dans le prompt système.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from config import CONTEXT_TOKEN_BUDGET
from src.api.cards import repository
from src.api.services import database

SECTIONS = ("main", "extra", "side")
SECTION_TITLES = {"main": "Main Deck", "extra": "Extra Deck", "side": "Side Deck"}

MAX_ENTRIES = 300
# Part maximale du budget de contexte que le deck peut occuper : le reste va
# à l'historique (voir ChatService._build_context).
MAX_DECK_SHARE = 0.75


class DeckError(Exception):
    """Fichier .ydk illisible, vide ou trop grand."""


@dataclass
class Deck:
    name: str
    # [{"card_id", "qty", "section"}], dans l'ordre du fichier.
    cards: List[Dict[str, Any]]
    # Données des cartes, par id (repository.get_by_card_ids).
    data: Dict[int, Dict[str, Any]]
    unresolved: List[str] = field(default_factory=list)

    def count(self, section: str) -> int:
        return sum(c["qty"] for c in self.cards if c["section"] == section)

    def summary(self) -> Dict[str, Any]:
        """Représentation renvoyée par l'API."""
        return {
            "name": self.name,
            "main": self.count("main"),
            "extra": self.count("extra"),
            "side": self.count("side"),
            "tokens": estimate_tokens(self.prompt_text()),
            "cards": [
                {
                    "id": c["card_id"], "qty": c["qty"], "section": c["section"],
                    "name": self.data[c["card_id"]]["name"],
                    "frame_type": self.data[c["card_id"]]["frame_type"],
                }
                for c in self.cards
            ],
            "unresolved": self.unresolved,
        }

    def prompt_text(self) -> str:
        """
        Texte ajouté au prompt système : liste du deck et texte officiel de
        chaque carte du Main et de l'Extra Deck (une seule fois par carte).
        Le Side Deck n'est listé que par les noms, pour économiser le contexte.
        """
        lines = [
            f'## Deck imported by the user: "{self.name}"',
            "The user imported this deck for the conversation. The card texts below are the official ones: "
            "rely on them rather than on your memory. A card missing from this list is not in the deck.",
        ]
        described: set = set()
        for section in SECTIONS:
            cards = [c for c in self.cards if c["section"] == section]
            if not cards:
                continue
            note = ", names only" if section == "side" else ""
            count = self.count(section)
            lines.append(f"\n### {SECTION_TITLES[section]} ({count} card{'s' if count > 1 else ''}{note})")
            for c in cards:
                card = self.data[c["card_id"]]
                if section == "side":
                    lines.append(f"{c['qty']}x {card['name']}")
                    continue
                lines.append(f"{c['qty']}x {card['name']} [{card_header(card)}]")
                if c["card_id"] not in described:
                    described.add(c["card_id"])
                    lines.append(" ".join(card["description"].replace("\r", "").split("\n")).strip())
        return "\n".join(lines)


def estimate_tokens(text: str | None) -> int:
    """Même estimation que chat.py : environ 4 caractères par token."""
    return len(text or "") // 4


def card_header(card: Dict[str, Any]) -> str:
    """Ligne de type compacte : « Effect Monster | DARK | Spellcaster | Level 4 | ATK 1800 | DEF 1000 »."""
    parts = [card.get("human_type") or card["type"]]
    if card["frame_type"] in ("spell", "trap"):
        return parts[0]

    def stat(value: int) -> str:
        return "?" if value == -1 else str(value)

    parts += [p for p in (card["attribute"], card["race"]) if p]
    if card["link_rating"] is not None:
        parts.append(f"Link-{card['link_rating']}")
    elif card["level"] is not None:
        parts.append(f"{'Rank' if card['frame_type'].startswith('xyz') else 'Level'} {card['level']}")
    if card["scale"] is not None:
        parts.append(f"Scale {card['scale']}")
    if card["atk"] is not None:
        parts.append(f"ATK {stat(card['atk'])}")
    if card["def"] is not None and card["link_rating"] is None:
        parts.append(f"DEF {stat(card['def'])}")
    if card["link_markers"]:
        parts.append("Arrows " + ", ".join(card["link_markers"]))
    return " | ".join(parts)


# ─── Lecture du .ydk ────────────────────────────────────────────────────────
# Un id de carte (ou d'artwork) par ligne, un exemplaire par ligne. Les lignes
# « #main », « #extra » et « !side » ouvrent les sections ; les autres lignes
# commençant par # ou ! sont des commentaires (« #created by ... »).

_YDK_HEADERS = {"#main": "main", "#extra": "extra", "!side": "side"}
# Chiffres ASCII uniquement, assez court pour un bigint.
_CARD_ID = re.compile(r"[0-9]{1,10}")


def parse_ydk(content: str) -> List[Tuple[str, int]]:
    """(section, id) de chaque exemplaire ; DeckError si ce n'est pas un .ydk."""
    entries: List[Tuple[str, int]] = []
    section = None
    for number, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if line.lower() in _YDK_HEADERS:
            section = _YDK_HEADERS[line.lower()]
        elif not line or line.startswith(("#", "!")):
            continue
        elif section is None or not _CARD_ID.fullmatch(line):
            raise DeckError(f"Not a valid .ydk file (line {number}).")
        else:
            entries.append((section, int(line)))
    if not entries:
        raise DeckError("No card found in this .ydk file.")
    if len(entries) > MAX_ENTRIES:
        raise DeckError(f"This .ydk file has more than {MAX_ENTRIES} cards.")
    return entries


# ─── Résolution dans la base ────────────────────────────────────────────────

async def resolve(name: str, entries: List[Tuple[str, int]]) -> Deck:
    """
    Trouve chaque id dans la base locale (les artworks alternatifs renvoient à
    leur carte) et regroupe les exemplaires. Les ids inconnus vont dans unresolved.
    """
    by_artwork = await repository.get_by_ids(list({card_id for _, card_id in entries}))

    totals: Dict[Tuple[int, str], int] = {}
    unresolved: List[str] = []
    for section, card_id in entries:
        card = by_artwork.get(card_id)
        if card is None:
            unresolved.append(str(card_id))
            continue
        key = (card["id"], section)
        totals[key] = totals.get(key, 0) + 1

    if not totals:
        raise DeckError("None of the cards of this .ydk file were found in the card database.")

    cards = [{"card_id": card_id, "qty": qty, "section": section} for (card_id, section), qty in totals.items()]
    data = await repository.get_by_card_ids([c["card_id"] for c in cards])
    return Deck(name=name, cards=cards, data=data, unresolved=list(dict.fromkeys(unresolved)))


# ─── Deck de la session ─────────────────────────────────────────────────────

async def import_deck(user_id: int, session_id: str, name: str, content: str) -> Deck:
    """
    Lit, résout et enregistre le deck de la session (DeckError si la liste est
    inutilisable, database.SessionOwnershipError si la session est à un autre).
    """
    deck = await resolve(name, parse_ydk(content))
    limit = int(CONTEXT_TOKEN_BUDGET * MAX_DECK_SHARE)
    tokens = estimate_tokens(deck.prompt_text())
    if tokens > limit:
        raise DeckError(
            f"This deck is too large for the model's context (about {tokens} tokens, "
            f"limit {limit}): raise CONTEXT_TOKEN_BUDGET together with the LLM context size."
        )
    await database.save_deck(user_id, session_id, name, deck.cards)
    return deck


async def load_deck(session_id: str, user_id: int) -> Deck | None:
    """Deck de la session, avec les données à jour des cartes (None s'il n'y en a pas)."""
    stored = await database.get_deck(session_id, user_id)
    if stored is None:
        return None
    data = await repository.get_by_card_ids([c["card_id"] for c in stored["cards"]])
    # Une carte retirée de la base depuis l'import est ignorée.
    cards = [c for c in stored["cards"] if c["card_id"] in data]
    return Deck(name=stored["name"], cards=cards, data=data)
