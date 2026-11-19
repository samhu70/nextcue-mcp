#!/usr/bin/env python3
"""Provide local Codex MCP headers; --save accepts the token without echoing it."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


TOKEN_FILE = Path.home() / ".codex" / "credentials" / "nextcue-token"


def is_link(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def windows_permissions(path, protect=False):
    script = """
$ErrorActionPreference = 'Stop'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$system = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$path = $env:NEXTCUE_PERMISSION_PATH
"""
    if protect:
        script += """
$directory = [System.IO.Directory]::Exists($path)
if ($directory) { $acl = [System.Security.AccessControl.DirectorySecurity]::new() }
else { $acl = [System.Security.AccessControl.FileSecurity]::new() }
$acl.SetOwner($user)
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in @($user, $system)) {
    if ($directory) { $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow') }
    else { $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow') }
    $acl.AddAccessRule($rule)
}
if ($directory) { [System.IO.Directory]::SetAccessControl($path, $acl) }
else { [System.IO.File]::SetAccessControl($path, $acl) }
"""
    else:
        script += """
if ([System.IO.Directory]::Exists($path)) { $acl = [System.IO.Directory]::GetAccessControl($path) }
else { $acl = [System.IO.File]::GetAccessControl($path) }
$owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -ne $user.Value -or -not $acl.AreAccessRulesProtected) { exit 1 }
foreach ($rule in $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
    if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($user.Value, $system.Value)) { exit 1 }
}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "NEXTCUE_PERMISSION_PATH": str(path)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=20,
    )
    if result.returncode:
        raise ValueError("The credential file permissions must allow only your account and Windows SYSTEM.")


def restrict_permissions(path):
    if os.name == "nt":
        windows_permissions(path, protect=True)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def check_private_file(path):
    if is_link(path) or is_link(path.parent) or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("The token must be stored in a regular private file.")
    if os.name == "nt":
        windows_permissions(path)
    elif stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Token file permissions must be 600.")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".nextcue-", dir=path.parent)
    try:
        if os.name == "nt":
            windows_permissions(Path(temporary), protect=True)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="Save a token through a hidden terminal prompt")
    args = parser.parse_args()
    try:
        if args.save:
            token = getpass.getpass("Paste your NextCue token (input hidden): ").strip()
        else:
            check_private_file(TOKEN_FILE)
            token = TOKEN_FILE.read_text().strip()
        if not re.fullmatch(r"nqc_[0-9a-f]{64}", token):
            raise ValueError("Invalid NextCue token format; copy the complete token from your account page.")
        if args.save:
            TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if is_link(TOKEN_FILE) or is_link(TOKEN_FILE.parent):
                raise ValueError("The token file and its directory cannot be symbolic links.")
            restrict_permissions(TOKEN_FILE.parent)
            atomic_write(TOKEN_FILE, (token + "\n").encode())
            print("NextCue token saved privately. Its value has not been printed.")
        else:
            print(json.dumps({"Authorization": "Bearer " + token}))
        return 0
    except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
        print(f"NextCue connection: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
