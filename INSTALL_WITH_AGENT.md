# Install NextCue MCP with an Agent

This guide is for the Agent doing the installation. Ask the user only for information or a local handoff that is actually missing. Use the existing installer; do not invent a separate config editor or collect a personal token in chat.

## Prepare in the background

1. Detect the local operating system and the MCP client. This kit configures a **local Codex client**. For another client, use its documented Streamable HTTP configuration rather than overwriting Codex files and declaring success.
2. Get the latest versioned client ZIP and `SHA256SUMS` from [GitHub Releases](https://github.com/samhu70/nextcue-mcp/releases/latest). Verify its SHA-256 before running code. Keep the version and result in your installation report, without credential contents.
3. Detect an existing Python 3.11+ interpreter, including `python3`, `python` or the Windows Python launcher. If it is missing, provision it through an official source or an already trusted package manager within your existing permissions. The Agent handles this step. If your environment requires approval or cannot install a runtime, explain that specific limitation instead of asking the user to follow developer setup instructions.
4. Extract the kit. Do not modify the user's other MCP servers, tool restrictions, account settings or registration permissions. Do not read unrelated credential files or uninstall an existing connection.

## Ask for missing information

Run `install.py` with the detected interpreter and `--agent`. It returns JSON without opening a prompt or changing files when information is missing:

```json
{"status":"input_required","field":"url","sensitive":false}
```

An existing NextCue address is detected automatically. If an address is missing, ask the user for their installation's HTTPS address, then rerun with `--agent --url https://their-installation.example`. Do not guess that the public product website is their private instance.

The installer reuses an existing private token only when the existing NextCue connection has the same instance URL. Otherwise it returns:

```json
{"status":"input_required","field":"token","sensitive":true,"handoff":"local_hidden_input","resume_with":"--token-file <private-file>"}
```

For a token request:

- Ask the user to create a personal MCP token on their own instance under **Account → Manage MCP connection tokens**. Google browser sign-in does not grant MCP access.
- Use the client's protected local credential-input facility when available. Alternatively, start `nextcue_mcp_headers.py --save` in an interactive terminal provided by the Agent, and let the user enter the token into its hidden prompt. The user does not need to type installation commands. If your Agent cannot expose a protected local input prompt, explain the single handoff required; do not pretend that ordinary chat input is secret storage.
- Do not request the token in chat, put it in a command-line argument, write it into a tool call, or print a credential file. Use the private file created by the hidden prompt, normally `~/.codex/credentials/nextcue-token`. Another private file explicitly supplied by the user can also be used. The installer checks permissions.

Resume with the detected interpreter:

```sh
python install.py --agent --url https://their-installation.example --token-file /absolute/path/to/private-token
```

`python` above means the interpreter you detected; use its actual executable path. Quote paths using the local platform's rules. The secret itself never appears in the command. The helper is installed in a permanent directory, so the downloaded folder can be removed after setup and verification.

## Interpret results and verify

| Exit code | JSON status | What to do |
| --- | --- | --- |
| 0 | `configured` | Config files are ready; verify the connection next. |
| 2 | `input_required` | Ask only for the named field or protected handoff, then resume. |
| 1 | `error` | Diagnose the non-secret error; do not delete configuration or weaken permissions. |

Configuration is backed up before an existing file is changed. Other servers and NextCue tool restrictions are preserved. Standard server tables are supported; symbolic-link targets, Windows junction targets and unsupported inline layouts are rejected before configuration changes.

On macOS/Linux, private token files use `600` permissions and their directory uses `700`. On Windows, the helper protects the file with a DACL limited to the current user and SYSTEM, and refuses a token file readable by other principals. It never places the token in `config.toml`. Do not bypass these checks or disable HTTPS certificate validation.

Reload the client's MCP connection if your tools support it. Otherwise ask for just the required client reload. Call `get_context`, confirm the expected account and workspace with the user, then use `search_tasks` for a read-only connection check. Do not create a test task or change business data. Report configuration and verified live access separately; a `configured` result alone does not prove that the server is reachable.

When a token expires, repeat the protected handoff and the same installer command. Do not repeatedly ask for an address or other information already known for that installation.
