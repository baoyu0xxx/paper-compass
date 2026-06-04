"""MCP JSON-RPC stdio loop and Chroma prewarm helpers."""

from __future__ import annotations

import json
import sys
import threading
from typing import Any, Callable, TextIO

from paper_compass.env_utils import PROJECT_ROOT

DEFAULT_VECTORDB_PATH = str(PROJECT_ROOT / "data" / "vectordb")
ToolHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


def _prewarm_collections(db_path: str = DEFAULT_VECTORDB_PATH) -> None:
    import chromadb as _cdb
    from chromadb.config import Settings as _CSet

    try:
        client = _cdb.PersistentClient(path=db_path, settings=_CSet(anonymized_telemetry=False))
    except Exception:
        return

    for prefix in ("wiki", "papers"):
        try:
            for collection in client.list_collections():
                if collection.name.startswith(prefix + "_") and collection.count() > 0:
                    collection.get(limit=1, include=["embeddings"])
                    break
        except Exception:
            pass


def mcp_stdio_mode(
    handle_tool: ToolHandler,
    *,
    version: str,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    db_path: str = DEFAULT_VECTORDB_PATH,
) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    initialized = False

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "paper-compass", "version": version},
                    "capabilities": {"tools": {}},
                },
            }
            print(json.dumps(response), file=stdout, flush=True)
            continue

        if method == "notifications/initialized":
            initialized = True
            threading.Thread(target=_prewarm_collections, kwargs={"db_path": db_path}, daemon=True).start()
            continue

        if not initialized:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32002, "message": "Server not initialized"},
            }
            print(json.dumps(response), file=stdout, flush=True)
            continue

        if method == "tools/list":
            from paper_compass.mcp_contracts import list_tools

            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools()}}
        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name", "")
            arguments = request.get("params", {}).get("arguments", {})
            try:
                result = handle_tool(tool_name, arguments)
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": f"Tool error: {exc}"},
                }
                print(json.dumps(response), file=stdout, flush=True)
                continue
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        print(json.dumps(response), file=stdout, flush=True)
