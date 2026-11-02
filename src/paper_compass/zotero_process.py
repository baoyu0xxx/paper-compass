"""Detect a running Zotero client without opening its database."""

from __future__ import annotations

import sys

PROCESS_NAMES = frozenset({"zotero.exe", "zotero-beta.exe"})


def zotero_running() -> bool:
    """Return True when a Zotero client process is present.

    Zotero keeps an exclusive lock on its live database while it runs, so a
    sync started now would only fail with ``database is locked``. The managed
    watcher uses this to defer such a round instead.

    Only Windows is inspected: the lock contention was observed there, and the
    process enumeration below is Win32-specific. Elsewhere this is always
    False, leaving the previous behaviour unchanged.
    """
    if sys.platform != "win32":
        return False
    return any(name.lower() in PROCESS_NAMES for name in _process_names())


def _process_names() -> set[str]:
    """Return the executable names of the running processes (empty on failure)."""
    try:
        return _win32_process_names()
    except OSError:
        # Failing to enumerate must never stop the watcher from syncing.
        return set()


def _win32_process_names() -> set[str]:
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")

    names: set[str] = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            names.add(entry.szExeFile)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names
