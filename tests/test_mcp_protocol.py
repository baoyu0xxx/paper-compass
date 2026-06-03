"""Protocol-level MCP stdio smoke tests using real JSON-RPC interactions.
Tests the full MCP lifecycle: initialize → initialized → tools/list → tools/call.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mcp_server.py"


def _start_server():
    env = os.environ.copy()
    env["PAPER_COMPASS_SKIP_RUNTIME_CHECK"] = "1"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    assert proc.stdout is not None
    assert proc.stdin is not None
    return proc


def _send_receive(proc, payload: dict, timeout: float = 5.0) -> dict:
    """Send a JSON-RPC request and return the parsed response. Retries on empty."""
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        line = line.strip()
        if line:
            return json.loads(line)
    raise TimeoutError(f"No response for {payload.get('method', '?')} within {timeout}s")


def test_mcp_full_lifecycle_smoke():
    """Full spec lifecycle: initialize → initialized → tools/list → tools/call."""
    proc = _start_server()

    # 1. Send initialize
    init_resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    })
    assert init_resp["jsonrpc"] == "2.0"
    assert init_resp["result"]["protocolVersion"] == "2024-11-05"
    assert init_resp["result"]["serverInfo"]["name"] == "paper-compass"
    assert "tools" in init_resp["result"]["capabilities"]

    # 2. Send initialized notification (no response expected, so just fire-and-forget)
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.flush()
    time.sleep(0.1)  # Small delay to let server process

    # 3. tools/list
    tools_resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    tools = tools_resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "search_library" in names
    assert "search_passages" in names
    assert "ask_research" in names

    # 4. tools/call
    call_resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_library",
            "arguments": {"query": "family firm", "limit": 2},
        },
    })
    text_payload = call_resp["result"]["content"][0]["text"]
    tool_result = json.loads(text_payload)
    assert tool_result["tool"] == "search_library"
    assert "ok" in tool_result
    assert "trace_id" in tool_result

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)


def test_mcp_rejects_request_before_initialized():
    """Server should reject tools/list before initialized notification."""
    proc = _start_server()

    # Send initialize
    _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "t", "version": "1"}},
    })

    # Try tools/list BEFORE initialized notification
    resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32002  # Server not initialized

    # Now send initialized
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.flush()
    time.sleep(0.1)

    # tools/list should now work
    resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {},
    })
    assert "result" in resp

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)


def test_mcp_unknown_method_returns_error():
    """Unknown method should return JSON-RPC -32601 error."""
    proc = _start_server()

    _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "t", "version": "1"}},
    })
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    proc.stdin.flush()
    time.sleep(0.1)

    resp = _send_receive(proc, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "nonexistent/method",
        "params": {},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32601

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)
