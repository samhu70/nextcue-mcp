# NextCue MCP client connection kit

Connect a local Codex client to **your existing NextCue installation**. Your Agent detects the existing connection, asks only for missing information and configures it automatically. The MCP server continues to run inside NextCue at `/mcp`.

[Download the latest connection kit](https://github.com/samhu70/nextcue-mcp/releases/latest) · [Website setup guide](https://nextcue.fivexing.com.au/support/mcp)

## Ask your Agent to install

Send your Agent this request:

> Install NextCue MCP from https://github.com/samhu70/nextcue-mcp. Prepare the environment and configure my local client automatically. Ask me for my NextCue address if it is missing. Use protected local input for the personal token; do not ask me to paste it into chat. Preserve my other MCP settings and verify the connection afterwards.

The Agent prepares the runtime and downloads in the background. You provide your private instance address and, when needed, a personal token through a local hidden prompt. The Agent handles the commands, paths, configuration and checks.

**Agents: follow [INSTALL_WITH_AGENT.md](INSTALL_WITH_AGENT.md).** The installer supports structured, noninteractive requests for missing information:

```sh
python install.py --agent
```

The client code supports macOS, Windows and Linux with Python 3.11+. The Agent detects or provisions the interpreter; the user does not need to set it up manually. A local Codex client supporting HTTP header helpers is required. The Agent's own permissions and ability to offer protected credential input still apply.

The installer detects an existing address and adds `/mcp` to your instance address, installs the helper in your Codex configuration directory and updates only the `nextcue` entry. It preserves other connections and existing NextCue tool restrictions. A private token is reused automatically only for an existing connection to the same instance.

The token stays in a private local credential file, outside `config.toml`. It is not printed by the installer. Programs running as your operating-system account can read it; this is not a system keychain. One NextCue token is stored per operating-system account. Connecting to another instance or replacing the token updates that saved token.

<details>
<summary>Advanced: run the interactive installer yourself</summary>

Sign in to your own NextCue instance, create a personal MCP token under **Account → Manage MCP connection tokens**, then run this in the extracted kit:

```sh
python install.py
```

Use the Python 3.11+ interpreter available on your system. Enter your HTTPS address and paste the token into the hidden prompt. Reload the MCP connection afterwards. You can delete the extracted folder after setup.

</details>

## Configuration backup and compatibility

Before updating an existing configuration, setup saves a private backup named `config.toml.nextcue-backup-<id>` beside it. Writes are atomic; if a later write fails, setup attempts to restore files already changed. Keep backups private because your existing configuration may contain other credentials.

Setup uses `~/.codex/config.toml`, or the configuration directory selected by an existing `CODEX_HOME` setting. Symbolic-link targets and unusual inline MCP table layouts are rejected before changes. Use the manual steps below if your configuration needs that layout. Old explicit Authorization headers and Bearer environment-variable settings for this `nextcue` entry are replaced by the token helper; other headers and tool permissions remain.

To undo setup, close Codex and restore the backup configuration. If you previously had a NextCue connection, running setup again replaced its local token; create/save the appropriate token for the restored installation before reconnecting.

## Renew or revoke access

Personal MCP tokens currently expire after 30 days. Ask your Agent to renew the connection using a replacement token from the same installation and the protected local input flow. You can also update just the token using the permanently installed helper:

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

The helper alone supports Python 3.8+; Windows uses its built-in PowerShell for private-file permissions. From the extracted folder, run `python3 nextcue_mcp_headers.py --save` and paste the token into its hidden prompt.

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
