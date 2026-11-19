"""Exercise setup with temporary files and synthetic tokens only."""

import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import install


TOKEN = "nqc_" + "a" * 64


class InstallerTests(unittest.TestCase):
    def test_addresses_are_normalized_and_unsafe_addresses_rejected(self):
        for url in ("https://nextcue.example.com", "https://nextcue.example.com/", "https://nextcue.example.com/mcp/"):
            self.assertEqual("https://nextcue.example.com/mcp", install.endpoint(url))
        self.assertEqual("https://[::1]:7063/mcp", install.endpoint("https://[::1]:7063"))
        for url in ("http://example.com", "https://user:pass@example.com", "https://example.com?token=secret", "https://example.com/#fragment", "https://example.com/Account/McpTokens", "https://example.com:bad", "https://example.com:", "https://exam\nple.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                install.endpoint(url)

    def test_updates_only_nextcue_and_keeps_restrictions_and_comments(self):
        original = '''# User settings stay intact.
model = "example-model"
[mcp_servers.other]
url = "https://other.example/mcp"
[mcp_servers."nextcue"]
url = "https://old.example/mcp"
disabled_tools = ["permanently_delete_task"]
bearer_token_env_var = "OLD_TOKEN"
[mcp_servers.nextcue.http_headers]
Authorization = "old-fake"
"X-Mode" = "retained"
[mcp_servers.nextcue.env_http_headers]
AUTHORIZATION = "OLD_ENV"
[mcp_servers.nextcue.tools.create_task]
approval_mode = "prompt"
[features]
example = true
'''
        result = install.configured_text(original, "https://new.example/mcp", "python3 '/a path/helper.py'")
        config = tomllib.loads(result)
        self.assertTrue(result.startswith('# User settings stay intact.\nmodel = "example-model"'))
        self.assertEqual(tomllib.loads(original)["mcp_servers"]["other"], config["mcp_servers"]["other"])
        self.assertEqual({"example": True}, config["features"])
        connection = config["mcp_servers"]["nextcue"]
        self.assertEqual(["permanently_delete_task"], connection["disabled_tools"])
        self.assertEqual({"X-Mode": "retained"}, connection["http_headers"])
        self.assertEqual({}, connection["env_http_headers"])
        self.assertEqual({"create_task": {"approval_mode": "prompt"}}, connection["tools"])
        self.assertNotIn("bearer_token_env_var", connection)
        self.assertEqual(config, tomllib.loads(install.configured_text(result, "https://new.example/mcp", connection["http_headers_helper"])))

    def test_inline_layout_or_table_text_in_multiline_string_fails_safely(self):
        for original in ('mcp_servers = { nextcue = { url = "https://old.example/mcp" } }\n', 'notes = """\n[mcp_servers.nextcue]\ntext\n"""\n'):
            with self.subTest(original=original), self.assertRaises(ValueError):
                install.configured_text(original, "https://new.example/mcp", "python3 helper.py")

    def test_install_backs_up_config_keeps_token_out_of_config_and_installs_permanently(self):
        with tempfile.TemporaryDirectory(prefix="nextcue setup ") as directory:
            root = Path(directory)
            config, token_file = root / "config.toml", root / "credentials/token"
            original = 'model = "retained"\n'
            config.write_text(original)
            backup = install.install("https://nextcue.example.com", TOKEN, config, token_file)
            self.assertEqual(original, backup.read_text())
            install.headers.check_private_file(backup)
            self.assertEqual(TOKEN, token_file.read_text().strip())
            install.headers.check_private_file(token_file)
            if os.name != "nt":
                self.assertEqual(0o700, token_file.parent.stat().st_mode & 0o777)
            self.assertNotIn(TOKEN, config.read_text())
            connection = tomllib.loads(config.read_text())["mcp_servers"]["nextcue"]
            self.assertEqual("https://nextcue.example.com/mcp", connection["url"])
            helper = (root / "nextcue/nextcue_mcp_headers.py").resolve()
            self.assertIn(str(helper), connection["http_headers_helper"])
            self.assertEqual(Path(install.headers.__file__).read_bytes(), helper.read_bytes())
            check = subprocess.run(connection["http_headers_helper"] + " --help", shell=True, capture_output=True, text=True, timeout=30, check=True)
            self.assertIn("--save", check.stdout)

    def test_fresh_install_and_invalid_token_without_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, token_file = root / "config.toml", root / "credentials/token"
            with self.assertRaises(ValueError):
                install.install("https://nextcue.example.com", "invalid", config, token_file)
            self.assertEqual([], list(root.iterdir()))
            self.assertIsNone(install.install("https://nextcue.example.com", TOKEN, config, token_file))
            install.headers.check_private_file(config)

    def test_symlink_config_is_rejected_without_changing_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.toml"
            target.write_text('model = "retained"\n')
            config, token_file = root / "config.toml", root / "token"
            config.symlink_to(target)
            token_file.write_text("previous")
            with self.assertRaises(ValueError):
                install.install("https://nextcue.example.com", TOKEN, config, token_file)
            self.assertEqual("previous", token_file.read_text())
            self.assertEqual('model = "retained"\n', target.read_text())

    def test_config_failure_rolls_back_helper_and_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, token_file = root / "config.toml", root / "credentials/token"
            config.write_text('model = "retained"\n')
            token_file.parent.mkdir()
            token_file.write_text("previous")
            real_write = install.atomic_write
            def fail_config(path, data):
                if path == config:
                    raise OSError("simulated write failure")
                real_write(path, data)
            with patch.object(install, "atomic_write", side_effect=fail_config), self.assertRaises(OSError):
                install.install("https://nextcue.example.com", TOKEN, config, token_file)
            self.assertEqual("previous", token_file.read_text())
            self.assertEqual('model = "retained"\n', config.read_text())
            self.assertFalse((root / "nextcue/nextcue_mcp_headers.py").exists())

    def test_main_hides_token_and_needs_only_two_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, token_file = root / "config.toml", root / "credentials/token"
            with patch("sys.argv", ["install"]), patch.object(install.headers, "TOKEN_FILE", token_file), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="https://nextcue.example.com") as address, patch.object(install.getpass, "getpass", return_value=TOKEN) as token, patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(0, install.main(root / "config.toml"))
            address.assert_called_once()
            token.assert_called_once()
            self.assertNotIn(TOKEN, output.getvalue())
            with patch.object(install.headers, "TOKEN_FILE", token_file), patch("sys.argv", ["helper"]), patch("sys.stdout", io.StringIO()) as header_output:
                self.assertEqual(0, install.headers.main())
            self.assertEqual({"Authorization": "Bearer " + TOKEN}, json.loads(header_output.getvalue()))

    def test_agent_requests_missing_input_without_writes_or_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for args, field in ((["install", "--agent"], "url"), (["install", "--agent", "--url", "https://nextcue.example.com"], "token")):
                with patch.object(install.headers, "TOKEN_FILE", root / "credentials/token"), patch("sys.argv", args), patch("builtins.input", side_effect=AssertionError("No prompts")), patch.object(install.getpass, "getpass", side_effect=AssertionError("No prompts")), patch("sys.stdout", io.StringIO()) as output:
                    self.assertEqual(2, install.main(root / "config.toml"))
                self.assertEqual(field, json.loads(output.getvalue())["field"])
            self.assertEqual([], list(root.iterdir()))

    def test_agent_private_file_setup_and_same_instance_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, token = root / "private-token", root / "credentials/token"
            install.atomic_write(source, TOKEN.encode())
            for extra in (["--token-file", str(source)], []):
                args = ["install", "--agent"] + (["--url", "https://nextcue.example.com"] + extra if extra else [])
                with patch.object(install.headers, "TOKEN_FILE", token), patch("sys.argv", args), patch("sys.stdout", io.StringIO()) as output:
                    self.assertEqual(0, install.main(root / "config.toml"))
                self.assertEqual("configured", json.loads(output.getvalue())["status"])
                self.assertNotIn(TOKEN, output.getvalue())
            with patch.object(install.headers, "TOKEN_FILE", token), patch("sys.argv", ["install", "--agent", "--url", "https://another.example.com"]), patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(2, install.main(root / "config.toml"))
            self.assertEqual("token", json.loads(output.getvalue())["field"])

    def test_agent_errors_do_not_expose_invalid_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private-token"
            invalid = "private-but-invalid-secret"
            install.atomic_write(source, invalid.encode())
            with patch.object(install.headers, "TOKEN_FILE", root / "credentials/token"), patch("sys.argv", ["install", "--agent", "--url", "https://nextcue.example.com", "--token-file", str(source)]), patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(1, install.main(root / "config.toml"))
            self.assertEqual("error", json.loads(output.getvalue())["status"])
            self.assertNotIn(invalid, output.getvalue())
            self.assertFalse((root / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
