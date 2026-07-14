
import sys
import asyncio
import itertools

SEPARATOR = "=" * 60
THIN_SEP  = "-" * 50
TABLE_W   = 115


def print_banner() -> None:
    print(f"{SEPARATOR}\n      M.A.I.A. - Cli Interface      \n{SEPARATOR}")


def print_response(text: str) -> None:
    sys.stdout.write(f"{THIN_SEP}\n{text}\n{THIN_SEP}")
    sys.stdout.flush()

async def wait_animation():
    frames = itertools.cycle([
    '[=    ]', '[==   ]', '[ ===  ]', '[  === ]', 
    '[   ==]', '[    =]', '[   ==]', '[  === ]', 
    '[ ===  ]', '[==   ]'
    ])

    try:
        while True:
            f = next(frames)
            sys.stdout.write(f'\r{f}')
            sys.stdout.flush()
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        sys.stdout.write('\r' + ' ' * 20 + '\r')
        sys.stdout.flush()
