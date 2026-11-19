# NextCue MCP client connection kit

Connect a local Codex client to **your existing NextCue installation**. The setup wizard asks for your installation address and personal token, then configures the connection for you. The MCP server continues to run inside NextCue at `/mcp`.

[Download the latest connection kit](https://github.com/samhu70/nextcue-mcp/releases/latest) · [Website setup guide](https://nextcue.fivexing.com.au/support/mcp)

## Quick setup

You need **macOS or Linux, Python 3.11 or newer, and a local Codex client** that supports HTTP header helpers. There are no Python package dependencies. Native Windows and remote-executor setup are not supported by this release.

1. Sign in to **your NextCue installation**. Open **Account → Manage MCP connection tokens** (`/Account/McpTokens`) and create a personal token. Keep your installation's HTTPS address handy. Connect to its VPN or private network if your administrator requires one.
2. Download and extract the release ZIP. Open a terminal in that folder and run:

   ```sh
   python3 install.py
   ```

   Enter your NextCue HTTPS address and paste the token into the hidden prompt. You do not need to find Python paths or edit configuration files.
3. Reload the MCP connection or reopen Codex. Ask it to call `get_context` and check your account and workspaces. Use `search_tasks` to check access without creating a task.

The wizard automatically adds `/mcp` to your instance address, installs the helper in your Codex configuration directory and updates only the `nextcue` entry in `config.toml`. Your other connections and existing NextCue tool restrictions are preserved. You can delete the extracted download folder afterwards.

The token is stored at `~/.codex/credentials/nextcue-token` with file permissions `600` and directory permissions `700`. It is never put in the configuration file or printed by the installer. This is a local file, not a system keychain; programs running as your operating-system account can read it. The helper supports one NextCue token per operating-system account. Running setup again replaces that token.

## Configuration backup and compatibility

Before updating an existing configuration, setup saves a private backup named `config.toml.nextcue-backup-<id>` beside it. Writes are atomic; if a later write fails, setup attempts to restore files already changed. Keep backups private because your existing configuration may contain other credentials.

Setup uses `~/.codex/config.toml`, or the configuration directory selected by an existing `CODEX_HOME` setting. Symbolic-link targets and unusual inline MCP table layouts are rejected before changes. Use the manual steps below if your configuration needs that layout. Old explicit Authorization headers and Bearer environment-variable settings for this `nextcue` entry are replaced by the token helper; other headers and tool permissions remain.

To undo setup, close Codex and restore the backup configuration. If you previously had a NextCue connection, running setup again replaced its local token; create/save the appropriate token for the restored installation before reconnecting.

## Renew or revoke access

Personal MCP tokens currently expire after 30 days. Create a replacement in the same installation and run `python3 install.py` again. You can also update just the token using the permanently installed helper:

```sh
python3 ~/.codex/nextcue/nextcue_mcp_headers.py --save
```

If you use a custom Codex configuration directory, use its `nextcue/nextcue_mcp_headers.py` file instead. Reload the client connection afterwards. Revoke unwanted tokens from the NextCue token page. Explicitly signing out of NextCue invalidates existing MCP tokens; closing a browser alone does not.

## Troubleshooting

- Check the instance address, private network/VPN access and trusted HTTPS certificate. Do not disable certificate verification. The public NextCue website is not your private instance.
- Check that the token belongs to this installation and has not expired or been revoked. Tokens cannot be transferred between installations.
- Check your Python version with `python3 --version`; the wizard needs Python 3.11+. Run setup in an interactive terminal so its token prompt can stay hidden.
- If setup refuses a custom configuration layout, use the manual steps below. Do not remove your existing configuration to force installation.
- The wizard configures files; a successful connection still requires your NextCue server and network to be available. Tool availability depends on the server version and your permissions.

<details>
<summary>Manual setup and other MCP clients</summary>

The helper alone still supports Python 3.8+ on macOS/Linux. From the extracted folder, run `python3 nextcue_mcp_headers.py --save` and paste the token into its hidden prompt.

Edit [codex.toml.example](codex.toml.example), replacing the instance URL and both absolute paths. Merge the table into `~/.codex/config.toml`; update an existing table instead of adding a duplicate. Preserve your other settings and keep the extracted helper in a permanent location. Reload the MCP connection.

The helper prints the Bearer header when called without `--save`; that mode is for the MCP client. Do not run it manually and paste its output into chats, issues or logs.

Other clients can use Streamable HTTP at `https://your-instance.example/mcp` and their own private `Authorization: Bearer <your-personal-token>` setting. The helper only works with local clients that support header commands. This kit does not add OAuth login.

See the [official Codex MCP configuration documentation](https://developers.openai.com/codex/mcp/).

</details>

## Verify downloads and run tests

Download `SHA256SUMS` beside the ZIP, then use `shasum -a 256 -c SHA256SUMS` on macOS, or `sha256sum -c SHA256SUMS` on Linux.

The tests use temporary files and synthetic tokens, without changing your real credentials:

```sh
python3 -m unittest -v test_install test_nextcue_mcp_headers
```

For support, contact [nextcue@fivexing.com.au](mailto:nextcue@fivexing.com.au). Keep tokens, passwords, private keys and workspace data out of public issues.
