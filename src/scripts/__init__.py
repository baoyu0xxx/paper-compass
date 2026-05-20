"""Compatibility shims for legacy console entrypoints.

Older paper-compass installs exposed console scripts pointing at
`scripts.run_mcp_server:main` and `scripts.healthcheck:main`.
The real implementations now live under `paper_compass.*`, but keeping
this package in the installed distribution lets stale wrappers continue
working after upgrade/reinstall.
"""
