#!/usr/bin/env python3
"""Configure a local Codex connection using an installation URL and personal token."""

import copy
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
import uuid

try:
    import tomllib
except ImportError:
    sys.exit("NextCue setup needs Python 3.11 or newer. Update Python, then run this file again.")

import nextcue_mcp_headers as headers


def endpoint(value):
    value = value.strip()
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ("", "/", "/mcp", "/mcp/")
            or any(c.isspace() or ord(c) < 32 for c in value) or parsed.netloc.endswith(":")):
        raise ValueError("Enter your installation's HTTPS address, such as https://nextcue.example.com.")
    parsed.port  # Validate a supplied port before changing any files.
    return urlunsplit(("https", parsed.netloc, "/mcp", "", ""))


def toml_value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(json.dumps(key) + " = " + toml_value(item) for key, item in value.items()) + " }"
    raise ValueError("An existing NextCue setting needs manual editing; no files have been changed.")


def configured_text(original, url, helper):
    before = tomllib.loads(original)
    expected = copy.deepcopy(before)
    connection = expected.setdefault("mcp_servers", {}).setdefault("nextcue", {})
    connection.update(url=url, http_headers_helper=helper, enabled=True)
    connection.pop("bearer_token_env_var", None)
    for key in ("http_headers", "env_http_headers"):
        if key in connection:
            connection[key] = {name: value for name, value in connection[key].items() if name.lower() != "authorization"}
    lines, kept, omit = original.splitlines(keepends=True), [], False
    # shortcut: edit standard server tables; unsupported inline layouts fail validation before any write.
    for line in lines:
        if re.match(r"^\s*\[.*\]\s*(?:#.*)?$", line):
            try:
                table = tomllib.loads(line + "\n__nextcue_setup_marker__ = true\n")
                omit = isinstance(table.get("mcp_servers", {}).get("nextcue"), dict)
            except (ValueError, TypeError, AttributeError):
                omit = False
        if not omit:
            kept.append(line)
    result = "".join(kept).rstrip() + "\n\n[mcp_servers.nextcue]\n"
    result += "".join(json.dumps(key) + " = " + toml_value(value) + "\n" for key, value in connection.items())
    try:
        matches = tomllib.loads(result) == expected
    except ValueError:
        matches = False
    if not matches:
        raise ValueError("Your config uses a layout the installer cannot safely update. No files have been changed; use the manual guide.")
    return result


def read_private_target(path):
    if path.is_symlink() or path.parent.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
        raise ValueError("A setup target is a symbolic link or special file. No files have been changed.")
    return path.read_bytes() if path.exists() else None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".nextcue-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(url, token, config, token_file):
    url = endpoint(url)
    if not re.fullmatch(r"nqc_[0-9a-f]{64}", token):
        raise ValueError("Invalid token. Copy the complete personal MCP token from your NextCue account.")
    helper = config.parent / "nextcue" / "nextcue_mcp_headers.py"
    originals = {path: read_private_target(path) for path in (config, token_file, helper)}
    original_config = originals[config] or b""
    helper_command = shlex.join([sys.executable, str(helper.resolve())])
    updated = configured_text(original_config.decode("utf-8"), url, helper_command).encode("utf-8")
    helper_bytes = Path(headers.__file__).read_bytes()
    backup = None
    if originals[config] is not None:
        backup = config.with_name("config.toml.nextcue-backup-" + uuid.uuid4().hex)
        atomic_write(backup, original_config)
    changed = []
    try:
        if read_private_target(config) != originals[config]:
            raise ValueError("Your configuration changed during setup. Run the installer again.")
        token_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        token_file.parent.chmod(0o700)
        for path, data in ((helper, helper_bytes), (token_file, (token + "\n").encode()), (config, updated)):
            if read_private_target(path) != originals[path]:
                raise ValueError("A setup file changed during installation. Run the installer again.")
            atomic_write(path, data)
            changed.append(path)
    except BaseException:
        for path in reversed(changed):
            if originals[path] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, originals[path])
        raise
    return backup


def main():
    try:
        if os.name != "posix":
            raise ValueError("This installer currently supports macOS and Linux.")
        if not sys.stdin.isatty():
            raise ValueError("Run this installer from an interactive terminal so your token can stay hidden.")
        print("NextCue setup — configure your local Codex connection.\nYour other connections are preserved; the existing NextCue token will be replaced.")
        url = endpoint(input("NextCue HTTPS address: "))
        token = getpass.getpass("Personal MCP token (input hidden): ").strip()
        config = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser() / "config.toml"
        backup = install(url, token, config, headers.TOKEN_FILE)
        print("NextCue is configured. Reload the MCP connection or reopen Codex, then ask it to call get_context.")
        print("You can delete the extracted download folder; the helper is installed in your Codex directory.")
        if backup:
            print("Previous configuration backup: " + str(backup))
        return 0
    except (OSError, ValueError, TypeError, AttributeError, EOFError, KeyboardInterrupt):
        print("NextCue setup did not finish. Check your HTTPS address, complete token, Python version and configuration layout. Your token has not been printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
