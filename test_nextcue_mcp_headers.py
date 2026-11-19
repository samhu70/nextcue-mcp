"""Checks the helper with fake credentials in an isolated home directory."""

import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("headers", Path(__file__).with_name("nextcue_mcp_headers.py"))
headers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headers)


class HeaderHelperTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows ACL test")
    def test_windows_private_acl_round_trip(self):
        run = headers.subprocess.run
        def checked_run(*args, **kwargs):
            kwargs["stderr"] = headers.subprocess.PIPE
            result = run(*args, **kwargs)
            if result.returncode:
                self.fail(result.stderr.decode(errors="replace"))
            return result
        with tempfile.TemporaryDirectory() as directory, patch.object(headers.subprocess, "run", side_effect=checked_run):
            path = Path(directory) / "private-file"
            headers.atomic_write(path, b"synthetic-data")
            headers.check_private_file(path)

    def test_missing_file_fails_without_header_output(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(headers, "TOKEN_FILE", Path(folder) / "missing"):
            with patch("sys.argv", ["helper"]), patch("sys.stderr", io.StringIO()), patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(1, headers.main())
            self.assertEqual("", output.getvalue())

    def test_invalid_input_does_not_replace_existing_token(self):
        fake = "nqc_" + "a" * 64
        with tempfile.TemporaryDirectory() as folder, patch.object(headers, "TOKEN_FILE", Path(folder) / "token"):
            headers.TOKEN_FILE.write_text(fake)
            with patch("sys.argv", ["helper", "--save"]), patch.object(headers.getpass, "getpass", return_value="invalid"), patch("sys.stderr", io.StringIO()), patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(1, headers.main())
            self.assertEqual("", output.getvalue())
            self.assertEqual(fake, headers.TOKEN_FILE.read_text())

    def test_symlink_is_rejected_for_read_and_save(self):
        fake = "nqc_" + "a" * 64
        with tempfile.TemporaryDirectory() as folder, patch.object(headers, "TOKEN_FILE", Path(folder) / "link"):
            target = Path(folder) / "target"
            target.write_text(fake)
            target.chmod(0o600)
            headers.TOKEN_FILE.symlink_to(target)
            for args in (["helper"], ["helper", "--save"]):
                with self.subTest(args=args), patch("sys.argv", args), patch.object(headers.getpass, "getpass", return_value="nqc_" + "b" * 64), patch("sys.stderr", io.StringIO()), patch("sys.stdout", io.StringIO()) as output:
                    self.assertEqual(1, headers.main())
                self.assertEqual("", output.getvalue())
                self.assertEqual(fake, target.read_text())

    def test_private_save_read_and_permission_rejection(self):
        fake = "nqc_" + "a" * 64
        with tempfile.TemporaryDirectory() as folder, patch.object(headers, "TOKEN_FILE", Path(folder) / "private" / "token"):
            output = io.StringIO()
            with patch("sys.argv", ["helper", "--save"]), patch.object(headers.getpass, "getpass", return_value=fake), patch("sys.stdout", output):
                self.assertEqual(0, headers.main())
            self.assertNotIn(fake, output.getvalue())
            headers.check_private_file(headers.TOKEN_FILE)
            output = io.StringIO()
            with patch("sys.argv", ["helper"]), patch("sys.stdout", output):
                self.assertEqual(0, headers.main())
            self.assertEqual({"Authorization": "Bearer " + fake}, json.loads(output.getvalue()))
            if os.name == "nt":
                headers.subprocess.run(["icacls", str(headers.TOKEN_FILE), "/grant", "*S-1-1-0:(R)"], check=True, stdout=headers.subprocess.DEVNULL, stderr=headers.subprocess.DEVNULL)
            else:
                headers.TOKEN_FILE.chmod(0o644)
            with patch("sys.argv", ["helper"]), patch("sys.stderr", io.StringIO()), patch("sys.stdout", io.StringIO()) as output:
                self.assertEqual(1, headers.main())
            self.assertEqual("", output.getvalue())


if __name__ == "__main__":
    unittest.main()
