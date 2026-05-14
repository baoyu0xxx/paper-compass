#!/bin/bash
# Hermes MCP launcher for paper-compass — ensures correct CWD
cd /mnt/d/pyproject/paper-compass
exec /mnt/d/pyproject/paper-compass/.venv/bin/python \
  /mnt/d/pyproject/paper-compass/scripts/run_mcp_server.py \
  --mcp "$@"
