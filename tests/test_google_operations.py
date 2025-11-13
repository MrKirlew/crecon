import sys
import types
import unittest

# Provide lightweight stubs for optional third-party packages so the
# backend modules can be imported in this minimal test environment.
if "pydantic_settings" not in sys.modules:
    stub = types.ModuleType("pydantic_settings")

    class BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    stub.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = stub

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class _Response:
        def __init__(self, status_code=200, text="", data=None):
            self.status_code = status_code
            self.text = text
            self._data = data or {}

        def json(self):
            return self._data

        @property
        def elapsed(self):
            class _Elapsed:
                def total_seconds(self_inner):
                    return 0.0

            return _Elapsed()

    class AsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def post(self, *args, **kwargs):
            return _Response()

        async def get(self, *args, **kwargs):
            return _Response()

    class TimeoutException(Exception):
        pass

    class RequestError(Exception):
        pass

    httpx_stub.AsyncClient = AsyncClient
    httpx_stub.TimeoutException = TimeoutException
    httpx_stub.RequestError = RequestError
    sys.modules["httpx"] = httpx_stub

from backend.google_functions import execute_google_function  # noqa: E402
from backend.n8n_bridge import N8NBridge  # noqa: E402
from config import settings as global_settings  # noqa: E402

setattr(global_settings, "n8n_webhook_secret", "test-secret")
setattr(global_settings, "n8n_webhook_url", "https://example.com/webhook")


class DummyBridge:
    def __init__(self):
        self.service_calls = []
        self.router_calls = []

    async def execute_service_operation(self, service, operation, parameters=None):
        self.service_calls.append((service, operation, parameters or {}))
        return {
            "success": True,
            "service": service,
            "operation": operation,
            "parameters": parameters or {}
        }

    async def execute_router_action(self, action, data=None, async_execution=False):
        self.router_calls.append((action, data or {}, async_execution))
        return {
            "success": True,
            "action": action,
            "data": data or {},
            "async_execution": async_execution
        }


class GoogleOperationsTests(unittest.IsolatedAsyncioTestCase):
    async def test_drive_operation_dispatches_to_bridge(self):
        bridge = DummyBridge()
        payload = {
            "operation": "search",
            "parameters": {"name": "Quarterly Report", "pageSize": 3}
        }

        result = await execute_google_function("drive_operation", payload, bridge)

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            bridge.service_calls,
            [("drive", "search", {"name": "Quarterly Report", "pageSize": 3})]
        )

    async def test_workspace_router_action_dispatches(self):
        bridge = DummyBridge()
        payload = {
            "action": "sheets.row.append",
            "data": {"spreadsheetId": "abc", "values": ["A", "B"]},
            "async": True
        }

        result = await execute_google_function("workspace_router_action", payload, bridge)

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            bridge.router_calls,
            [("sheets.row.append", {"spreadsheetId": "abc", "values": ["A", "B"]}, True)]
        )

    async def test_missing_operation_returns_error(self):
        bridge = DummyBridge()

        result = await execute_google_function("drive_operation", {}, bridge)

        self.assertEqual(result["status"], "error")
        self.assertIn("operation is required", result["error"])

    async def test_execute_service_operation_builds_payload(self):
        bridge = N8NBridge()
        captured = {}

        async def fake_post(endpoint, payload, timeout=None):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            return {"success": True}

        bridge._post_webhook = fake_post  # type: ignore[attr-defined]

        await bridge.execute_service_operation("gmail", "thread.list", {"maxResults": 5})

        self.assertEqual(captured["endpoint"], "gmail")
        body = captured["payload"]["body"]["data"]
        self.assertEqual(body["operation"], "thread.list")
        self.assertEqual(body["maxResults"], 5)

    async def test_execute_router_action_includes_root(self):
        bridge = N8NBridge()
        captured = {}

        async def fake_post(endpoint, payload, timeout=None):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            return {"success": True}

        bridge._post_webhook = fake_post  # type: ignore[attr-defined]

        await bridge.execute_router_action(
            action="calendar.event.list",
            data={"maxResults": 2},
            async_execution=False
        )

        self.assertEqual(captured["endpoint"], "workspace-router")
        body = captured["payload"]["body"]
        self.assertEqual(body["action"], "calendar.event.list")
        self.assertEqual(body["data"]["maxResults"], 2)
        self.assertEqual(captured["payload"]["action"], "calendar.event.list")
        self.assertEqual(captured["payload"]["data"]["maxResults"], 2)


if __name__ == "__main__":
    unittest.main()
