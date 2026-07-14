
import sys

SEPARATOR = "=" * 60
THIN_SEP  = "-" * 50
TABLE_W   = 115


def print_banner() -> None:
    print(f"{SEPARATOR}\n      M.A.I.A. - Cli Interface      \n{SEPARATOR}")


def print_response(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()

