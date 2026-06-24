"""
Responsabilité unique : tout ce qui touche stdout / rendu terminal.
Aucune logique métier, aucun appel réseau.
"""

import sys
from src.schemas import PerfSummary

SEPARATOR = "=" * 60
THIN_SEP  = "-" * 50
TABLE_W   = 115


def print_banner() -> None:
    print(f"{SEPARATOR}\n      M.A.I.A. - Cli Interface      \n{SEPARATOR}")


def print_routing_start() -> None:
    print(f"[Routeur] Démarrage des agents...\n{THIN_SEP}")


def print_routing_end() -> None:
    print(f"\n{THIN_SEP}\n[Routeur] Fin du streaming. Analyse du tableau de bord...")


def stream_text(text: str, node_name: str) -> None:
    """Écrit un chunk de texte en le préfixant à chaque nouvelle ligne."""
    clean = text.replace("\n", f"\n[{node_name}] ")
    sys.stdout.write(clean)
    sys.stdout.flush()


def print_stream_error(node_name: str, expert_type: str, error: str) -> None:
    print(f"\n[Échec] Noeud [{node_name}] ({expert_type}) -> {error}")


def print_perf_table(summaries: list[PerfSummary]) -> None:
    if not summaries:
        return
    header = (
        f"{'NOEUD':<13} | {'EXPERT':<10} | {'VITESSE':<9} | {'VOLUME':<8} | "
        f"{'TTFT':<7} | {'LOAD':<6} | {'RÉSEAU':<7} | {'TOTAL':<6} | {'MATÉRIEL':<25}"
    )
    print(f"\n{'='*TABLE_W}")
    print(header)
    print(f"{'-'*TABLE_W}")
    for p in summaries:
        print(
            f"{p.node:<13} | {p.expert:<10} | {p.t_s:<9} | {p.count:<8} | "
            f"{p.ttft:<7} | {p.load:<6} | {p.net:<7} | {p.total:<6} | {p.hardware:<25}"
        )
    print(f"{'='*TABLE_W}\n")


def print_final_answer(answer: str) -> None:
    print(f"\n[MAIA SYNTHÈSE FINALE] :\n{answer}\n{THIN_SEP}")