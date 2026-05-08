"""Protocol-level MCP stdio smoke tests using real JSON-RPC interactions."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mcp_server.py"


def test_mcp_stdio_tools_list_and_tools_call_smoke():
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ROOT),
    )

    assert proc.stdout is not None
    assert proc.stdin is not None

    # server prints one initialization response line first
    init_line = proc.stdout.readline().strip()
    assert init_line
    init = json.loads(init_line)
    assert init.get("jsonrpc") == "2.0"
    assert "serverInfo" in init.get("result", {})

    req_tools_list = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    proc.stdin.write(json.dumps(req_tools_list) + "\n")
    proc.stdin.flush()

    tools_list_line = proc.stdout.readline().strip()
    assert tools_list_line
    tools_resp = json.loads(tools_list_line)
    tools = tools_resp["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "search_library" in names
    assert "ask_research" in names

    req_tools_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_library",
            "arguments": {"query": "family firm", "limit": 2},
        },
    }
    proc.stdin.write(json.dumps(req_tools_call) + "\n")
    proc.stdin.flush()

    call_line = proc.stdout.readline().strip()
    assert call_line
    call_resp = json.loads(call_line)
    text_payload = call_resp["result"]["content"][0]["text"]
    tool_result = json.loads(text_payload)
    assert tool_result["tool"] == "search_library"
    assert "ok" in tool_result
    assert "trace_id" in tool_result

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)
