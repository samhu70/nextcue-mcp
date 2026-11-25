"""Local protocol/transport tests use only synthetic credentials and in-memory responses."""

import io
import json
import os
from pathlib import Path
from http.client import IncompleteRead
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import nextcue_mcp_server as local
import nextcue_mcp_headers as credentials

TOKEN = "nqc_" + "b" * 64


class Response(io.BytesIO):
    def __init__(self, value, code=200):
        super().__init__(json.dumps(value).encode() if not isinstance(value, bytes) else value)
        self.code = code


class Opener:
    def __init__(self, *responses):
        self.responses, self.calls = iter(responses), []

    def open(self, request, timeout):
        self.calls.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class FakeApi:
    def capabilities(self):
        return {"get_context", "get_task", "get_team_duty_history"}

    def request(self, path, args):
        if path.endswith("get_team_duty_history"):
            return [{"version": 1}], False
        if path.endswith("get_task"):
            raise local.ApiFailure("not_found", "Task not found.")
        return {"userId": "test-user"}, False


class ServerTests(unittest.TestCase):
    def config(self, root):
        token = root / "token"
        credentials.atomic_write(token, TOKEN.encode())
        value = {"url": "https://instance.example/api/v1", "tokenFile": str(token), "headers": {}, "envHeaders": {}}
        config = root / "connection.json"
        credentials.atomic_write(config, json.dumps(value).encode())
        return config, value

    def test_private_config_and_url_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, value = self.config(root)
            self.assertEqual(value, local.read_connection(config))
            for address in ("http://instance.example", "https://user:password@instance.example", "https://instance.example?token=x", "https://instance.example/api/v2", "https://instance.example/#fragment"):
                with self.subTest(address=address), self.assertRaises(ValueError):
                    local.api_url(address)
            for key in ("Authorization", "Host", "Content-Length", "Transfer-Encoding"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    local.validate_connection(value | {"headers": {key: "unsafe"}})
            with self.assertRaises(ValueError):
                local.validate_connection(value | {"headers": {"X-Test": "unsafe\r\nInjected: yes"}})
            if os.name != "nt":
                config.chmod(0o644)
                with self.assertRaises(ValueError):
                    local.read_connection(config)

    def test_api_uses_https_bearer_post_without_logging_or_retrying(self):
        with tempfile.TemporaryDirectory() as directory:
            _, value = self.config(Path(directory))
            opener = Opener(Response({"apiVersion": 1, "operations": ["get_context"]}), Response({"userId": "actor"}))
            api = local.InstanceApi(value, opener)
            self.assertEqual({"get_context"}, api.capabilities())
            self.assertEqual(({"userId": "actor"}, False), api.request("/operations/get_context", {}))
            self.assertIsNone(opener.calls[0].data)
            self.assertEqual(b"{}", opener.calls[1].data)
            self.assertEqual("Bearer " + TOKEN, opener.calls[1].get_header("Authorization"))
            self.assertEqual("https://instance.example/api/v1/operations/get_context", opener.calls[1].full_url)
            self.assertEqual(2, len(opener.calls))

    def test_errors_redirects_missing_api_and_network_failures_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            _, value = self.config(Path(directory))
            for status, code in ((301, "redirect_refused"), (307, "redirect_refused"), (401, "unauthorized"), (404, "server_upgrade_required"), (503, "instance_unavailable")):
                error = HTTPError(value["url"], status, "Error", {}, io.BytesIO(TOKEN.encode()))
                opener = Opener(error)
                with self.subTest(status=status), self.assertRaises(local.ApiFailure) as caught:
                    local.InstanceApi(value, opener).request("/operations/create_task", {})
                self.assertEqual(code, caught.exception.body["error"]["code"])
                self.assertNotIn(TOKEN, json.dumps(caught.exception.body))
                self.assertEqual(1, len(opener.calls))
            opener = Opener(URLError(TOKEN))
            with self.assertRaises(local.ApiFailure) as caught:
                local.InstanceApi(value, opener).request("/operations/create_task", {})
            self.assertIn("may have committed", caught.exception.body["error"]["message"])
            self.assertEqual(1, len(opener.calls))
            self.assertIsNone(local.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_interrupted_response_has_uncertain_write_error_and_no_retry(self):
        class Interrupted(Response):
            def read(self, size):
                raise IncompleteRead(b"synthetic", 100)
        with tempfile.TemporaryDirectory() as directory:
            _, value = self.config(Path(directory))
            opener = Opener(Interrupted({}))
            with self.assertRaises(local.ApiFailure) as caught:
                local.InstanceApi(value, opener).request("/operations/create_task", {})
            self.assertIn("may have committed", caught.exception.body["error"]["message"])
            self.assertEqual(1, len(opener.calls))

    def test_structured_business_errors_and_header_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            _, value = self.config(Path(directory))
            body = {"error": {"code": "version_conflict", "message": "Read again."}}
            error = HTTPError(value["url"], 409, "Conflict", {}, io.BytesIO(json.dumps(body).encode()))
            opener = Opener(error)
            value["headers"] = {"X-Mode": "retained"}
            value["envHeaders"] = {"X-Gateway": "NEXTCUE_TEST_GATEWAY"}
            with patch.dict(os.environ, {"NEXTCUE_TEST_GATEWAY": "synthetic"}):
                self.assertEqual((body, True), local.InstanceApi(value, opener).request("/operations/update_task", {}))
            self.assertEqual("retained", opener.calls[0].get_header("X-mode"))
            self.assertEqual("synthetic", opener.calls[0].get_header("X-gateway"))
            with patch.dict(os.environ, {"NEXTCUE_TEST_GATEWAY": "bad\nvalue"}), self.assertRaises(local.ApiFailure):
                local.InstanceApi(value, Opener()).request("/operations/get_context", {})

    def test_capability_intersection_and_unsupported_version(self):
        server = local.Server(FakeApi())
        server.initialized = True
        tools = server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["tools"]
        self.assertEqual({"get_context", "get_task", "get_team_duty_history"}, {tool["name"] for tool in tools})
        self.assertTrue(next(tool for tool in tools if tool["name"] == "get_task")["annotations"]["readOnlyHint"])
        with tempfile.TemporaryDirectory() as directory:
            _, value = self.config(Path(directory))
            with self.assertRaises(local.ApiFailure):
                local.InstanceApi(value, Opener(Response({"apiVersion": 2, "operations": []}))).capabilities()

    def test_backup_tools_are_capability_gated_and_queued_is_not_completion(self):
        class BackupApi:
            def __init__(self): self.calls = []
            def capabilities(self): return {"request_local_backup", "get_local_backup_status"}
            def request(self, path, arguments):
                self.calls.append((path, arguments))
                return {"requestId": arguments["requestId"], "requestState": "queued", "automaticBackups": False, "keepLast": 3}, False
        api = BackupApi()
        server = local.Server(api)
        server.initialized = True
        tools = server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["tools"]
        self.assertEqual(2, len(tools))
        write = next(tool for tool in tools if tool["name"] == "request_local_backup")
        self.assertFalse(write["annotations"]["readOnlyHint"])
        self.assertTrue(write["annotations"]["destructiveHint"])
        self.assertIn("queued is not completion", write["description"].replace("Acceptance/queued is not completion", "queued is not completion"))
        identifier = "11111111-2222-4333-8444-555555555555"
        result = server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "request_local_backup", "arguments": {"requestId": identifier}}})
        self.assertEqual("queued", result["structuredContent"]["requestState"])
        self.assertEqual([("/operations/request_local_backup", {"requestId": identifier})], api.calls)

    def test_handshake_notifications_ping_calls_and_eof_have_clean_stdio(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_context", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_task", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_team_duty_history", "arguments": {}}},
        ]
        output = io.BytesIO()
        local.serve(local.Server(FakeApi()), io.BytesIO(b"".join(json.dumps(message).encode() + b"\n" for message in messages)), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([1, 2, 3, 4, 5, 6], [response["id"] for response in responses])
        self.assertEqual("0.6.0", responses[0]["result"]["serverInfo"]["version"])
        self.assertEqual("test-user", responses[3]["result"]["structuredContent"]["userId"])
        self.assertTrue(responses[4]["result"]["isError"])
        self.assertNotIn("structuredContent", responses[5]["result"])
        self.assertEqual([{"version": 1}], json.loads(responses[5]["result"]["content"][0]["text"]))
        self.assertNotIn(TOKEN, output.getvalue().decode())

    def test_invalid_messages_never_echo_input_or_execute_unknown_tools(self):
        server = local.Server(FakeApi())
        output = io.BytesIO()
        lines = [b"invalid-" + TOKEN.encode(), b"[]", b'{"jsonrpc":"2.0","id":1,"method":"ping","method":"tools/call"}', b"[" * 2000 + b"]" * 2000,
                 json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "../unsafe", "arguments": {}}}).encode()]
        local.serve(server, io.BytesIO(b"\n".join(lines) + b"\n"), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(5, len(responses))
        self.assertTrue(all("error" in response for response in responses))
        self.assertNotIn(TOKEN, output.getvalue().decode())

    def test_actual_process_initializes_and_exits_on_eof_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            config, _ = self.config(Path(directory))
            request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2099-01-01", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
            result = subprocess.run([sys.executable, str(Path(local.__file__).resolve()), "--config", str(config)],
                                    input=json.dumps(request) + "\n", capture_output=True, text=True, timeout=30, check=True)
            response = json.loads(result.stdout)
            self.assertEqual("2025-11-25", response["result"]["protocolVersion"])
            self.assertEqual("", result.stderr)
            self.assertNotIn(TOKEN, result.stdout)


if __name__ == "__main__":
    unittest.main()
