"""Generate local-only credentials without printing them. Requires only Python's stdlib."""

import argparse
import os
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--mode", choices=["public", "synthetic"], required=True)
    args = parser.parse_args()
    if args.path.is_symlink():
        parser.error("Environment file must not be a symlink")
    if args.path.exists():
        if args.path.stat().st_mode & 0o077:
            parser.error("Existing environment file must be private (permission 600)")
        fields = dict(line.split("=", 1) for line in args.path.read_text().splitlines())
        if fields.get("CLEARPATH_DATA_MODE") != args.mode:
            parser.error("Existing environment file has a different data mode")
        return
    password = secrets.token_hex(32)
    content = "\n".join(
        [
            "POSTGRES_USER=clearpath",
            "POSTGRES_DB=clearpath",
            f"POSTGRES_PASSWORD={password}",
            f"CLEARPATH_API_KEY={secrets.token_hex(32)}",
            f"DATABASE_URL=postgresql+psycopg://clearpath:{password}@db:5432/clearpath",
            f"CLEARPATH_DATA_MODE={args.mode}",
            f"BACKEND_API_PORT={8001 if args.mode == 'synthetic' else 8000}",
            f"BACKEND_DB_PORT={55433 if args.mode == 'synthetic' else 55432}",
            "",
        ]
    )
    try:
        descriptor = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error("Environment file appeared concurrently; run again")
    with os.fdopen(descriptor, "w") as output:
        output.write(content)


if __name__ == "__main__":
    main()
