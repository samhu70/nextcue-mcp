# NextCue local MCP server

Connect your AI client to **your existing NextCue installation** through a local MCP server. The client launches this Python process over stdio; it calls your instance's authenticated HTTPS JSON API. Tool definitions run locally, while business rules, authorization and data stay on your DELL, NAS or other NextCue host.

[Download v0.5.0](https://github.com/samhu70/nextcue-mcp/releases/tag/v0.5.0) · [Agent setup](INSTALL_WITH_AGENT.md) · [44-tool workflow guide](MCP_CAPABILITIES.md)

```text
AI client → local NextCue MCP process → HTTPS /api/v1 → your NextCue instance
```

**Upgrade the instance first:** v0.5.0 requires NextCue instance API v1, first supplied by `20261122-2-preview.1` (Preview15). Installation checks authenticated API capabilities before switching configuration. An older or unreachable instance leaves the existing configuration/token intact. Existing remote `/mcp` connections continue working on compatible instances; v0.4.0 remains available for those connections.

## Ask your Agent to install

> Install NextCue MCP from https://github.com/samhu70/nextcue-mcp. Prepare the environment and configure my local client automatically. Ask me for my NextCue address if it is missing. Use protected local input for the personal token; do not ask me to paste it into chat. Preserve my other MCP settings and verify the connection afterwards.

**Agents: follow [INSTALL_WITH_AGENT.md](INSTALL_WITH_AGENT.md).** The Agent provisions Python 3.11+ when needed and runs `python install.py --agent`. Missing address or protected token input is requested through structured JSON. Setup supports macOS, Windows and Linux and configures a local Codex client. Other MCP clients can launch the same stdio process using their own command/args settings.

The installer detects an existing remote or local connection, reuses a private token only for the same instance, installs the server/manifest/credential helper permanently, verifies API v1 and replaces only the `nextcue` transport. Other connections, tool allowlists/denylists and per-tool approval settings are preserved. Custom transport headers are moved into private connection configuration. Unsupported layouts, symbolic-link targets and Windows junctions are rejected. No local listening port, Docker or additional Python package is needed.

The installer backs up an existing `config.toml` as `config.toml.nextcue-backup-<id>`, uses atomic file writes and restores changed files if a later step or API preflight fails. Configuration success and verified business access are reported separately; setup never creates a test task.

## Private connection configuration

Setup installs `nextcue_mcp_server.py`, `tools.json`, `nextcue_mcp_headers.py` and private `connection.json` under the selected Codex configuration directory's `nextcue/` folder. The generated `config.toml` uses `command` and `args`, without a URL or plaintext token. [codex.toml.example](codex.toml.example) shows the format.

A private `connection.json` contains:

```json
{
  "url": "https://your-instance.example/api/v1",
  "tokenFile": "/absolute/path/to/private/nextcue-token",
  "headers": {},
  "envHeaders": {}
}
```

The token stays in a separate private file. macOS/Linux use 600 file permissions; Windows permits the current user and SYSTEM only. These are filesystem protections, not a system keychain: programs running as your account can read the files. Configuration, logs and chat must never contain the token itself. HTTPS certificates are verified and redirects are refused, preventing a redirect from forwarding credentials elsewhere.

Setup manages one `nextcue` connection and one saved token per operating-system account. For manually configured multiple instances, use distinct protected connection/token files and separate MCP entries, each launching this server with its own `--config` path. Tokens belong to the instance that issued them.

## Verify or renew

With the Python interpreter used during setup:

```sh
python /absolute/path/to/nextcue_mcp_server.py --config /absolute/path/to/connection.json --check
```

This checks API v1 and authenticated `get_context` without changing business data. Reload the MCP connection, confirm your expected account/workspace, and perform a read-only query. Only locally known tools supported by the instance are advertised; the instance rechecks every operation's permissions.

Personal tokens currently expire after 30 days. Ask your Agent to renew using the same installer and protected input flow, or use the installed `nextcue_mcp_headers.py --save` helper for the default credential location. Explicit sign-out revokes existing tokens; closing a browser alone does not. A token cannot be transferred to a different installation.

To undo a successful migration, close the client and restore the private configuration backup. If a token was replaced, restore the appropriate protected credential as well. Keep the local server files when the restored configuration still references them.

## Transport and failure behavior

The server supports the MCP initialize lifecycle for `2025-11-25`, `2025-06-18` and `2025-03-26`, using newline-delimited JSON-RPC over stdio. stdout contains protocol messages only. It offers tools, without resources, prompts, background tasks or HTTP proxy fallback. Requests execute serially. The process exits on stdin EOF.

Business calls use `POST /api/v1/operations/<name>` and return the same task/record/duty contracts documented in [MCP_CAPABILITIES.md](MCP_CAPABILITIES.md). Local tool descriptions can be upgraded independently of the instance; genuinely new business operations still need a corresponding instance API upgrade. Non-object results remain JSON text without an object-only `structuredContent` field.

Writes are **never automatically retried**. After a timeout, broken response or version conflict, read the object/history before deciding another action; the first write may have committed. Ordinary task/record requestId rules remain, and the new business tools retain their existing version checks without replay receipts.

## Downloads and development tests

Download the ZIP and `SHA256SUMS` from the same Release. Verify with `shasum -a 256 -c SHA256SUMS` on macOS or `sha256sum -c SHA256SUMS` on Linux. The ZIP contains source, tool definitions and guides, without tokens or instance data.

```sh
python3 -m unittest -v test_install test_nextcue_mcp_headers test_nextcue_mcp_server
```

Tests use temporary files and synthetic credentials, exercising stdio, HTTP failures, safe migration/rollback and Windows ACL protection. For support, contact [nextcue@fivexing.com.au](mailto:nextcue@fivexing.com.au).
