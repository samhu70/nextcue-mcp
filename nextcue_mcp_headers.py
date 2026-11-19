#!/usr/bin/env python3
"""Provide local Codex MCP headers; --save accepts the token without echoing it."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys


TOKEN_FILE = Path.home() / ".codex" / "credentials" / "nextcue-token"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="Save a token through a hidden terminal prompt")
    args = parser.parse_args()
    try:
        if args.save:
            token = getpass.getpass("Paste your NextCue token (input hidden): ").strip()
        else:
            mode = TOKEN_FILE.stat().st_mode
            if TOKEN_FILE.is_symlink() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
                raise ValueError("Token file must be a regular private file with permissions 600.")
            token = TOKEN_FILE.read_text().strip()
        if not re.fullmatch(r"nqc_[0-9a-f]{64}", token):
            raise ValueError("Invalid NextCue token format; copy the complete token from your account page.")
        if args.save:
            TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            TOKEN_FILE.parent.chmod(0o700)
            descriptor = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(token + "\n")
            print("NextCue token saved privately. Its value has not been printed.")
        else:
            print(json.dumps({"Authorization": "Bearer " + token}))
        return 0
    except (OSError, ValueError, EOFError) as error:
        print(f"NextCue connection: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
