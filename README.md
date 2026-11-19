# NextCue MCP client connection kit

Connect a local MCP client to **your existing NextCue installation**. This kit includes a Python token helper and a Codex configuration template. The MCP server runs inside NextCue at `/mcp`; this download does not install a server or contain your workspace data.

[Download the latest connection kit](https://github.com/samhu70/nextcue-mcp/releases/latest) · [NextCue website](https://nextcue.fivexing.com.au/)

## Requirements

- An existing NextCue installation reachable over trusted HTTPS, including any private network or VPN access required by its administrator.
- Your own NextCue account and a personal MCP connection token from that installation.
- For the included helper: macOS or Linux, Python 3.8 or newer, and a local Codex client supporting `http_headers_helper`. The helper uses POSIX file permissions and is not supported on native Windows.

There are no Python package dependencies. Other clients can connect directly if they support Streamable HTTP and a securely configured Bearer header.

## Set up Codex

1. Download and extract the release ZIP into a permanent directory. If you move it later, update the helper path in your client configuration. You can verify the download with `shasum -a 256 -c SHA256SUMS` (macOS) or `sha256sum -c SHA256SUMS` (Linux), with both release assets in the same directory.
2. Sign in to **your NextCue installation**, then open **Account → Manage MCP connection tokens** (`/Account/McpTokens`). Create a token. The public NextCue website does not issue your instance's tokens.
3. From the extracted directory, save it through the hidden terminal prompt:

   ```sh
   python3 nextcue_mcp_headers.py --save
   ```

   The token is not echoed. It is stored at `~/.codex/credentials/nextcue-token`, with directory permissions `700` and file permissions `600`. This is a local file, not an operating-system keychain; programs running as your account can read it. Saving replaces the token previously stored by this helper. The kit supports one NextCue token per operating-system account.

4. Use `command -v python3` to find your Python executable. Edit `codex.toml.example`, replacing the example instance URL and both absolute paths. Merge the resulting `[mcp_servers.nextcue]` table into `~/.codex/config.toml`. If that table already exists, update it instead of adding a duplicate; preserve your other client settings.
5. Reload your client's MCP connection, or reopen the client if needed. Check that `get_context` returns your expected account and workspaces. You can then use `search_tasks` to check access without creating data. Tool availability depends on the installed NextCue server version and your workspace permissions.

The helper prints the Bearer header when called without `--save`; that mode is for the MCP client. Do not run it manually and paste its output into chat, issues, or logs.

## Configuration template

See [codex.toml.example](codex.toml.example). The example paths are placeholders, and `nextcue.example.com` must be replaced with your own installation's HTTPS hostname.

Codex's header helper is for connections made from the local environment. It does not run on a remote executor. Remove an old explicit Bearer or OAuth credential for this entry if it overrides the helper. See the [official Codex MCP configuration documentation](https://developers.openai.com/codex/mcp/).

## Other MCP clients

Configure Streamable HTTP with your installation's URL, such as `https://nextcue.example.com/mcp`, and set `Authorization: Bearer <your-personal-token>` using the client's private credential facility. The included Python helper is only useful if that client supports commands that return header JSON. This package does not add OAuth support to NextCue's personal-token endpoint.

## Renew or revoke access

NextCue personal MCP tokens currently expire after 30 days. Create a replacement in the same installation, run the `--save` command again, and reload the connection. You can revoke tokens from the NextCue token management page. Explicitly signing out of NextCue invalidates existing MCP tokens; closing a browser alone does not.

For connection errors, first check the installation URL, network access and trusted HTTPS certificate. For authentication errors, check that the token belongs to that installation and has not expired or been revoked. Do not disable certificate verification. Tokens from one NextCue installation do not authenticate to another.

## Tests and support

Run the isolated tests without reading or changing your real credentials:

```sh
python3 -m unittest -v test_nextcue_mcp_headers
```

For product support, contact [nextcue@fivexing.com.au](mailto:nextcue@fivexing.com.au). Keep tokens, passwords, private keys and workspace data out of public issues.
