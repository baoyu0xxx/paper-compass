"""Keep spawned child processes from flashing a console window on Windows."""

from __future__ import annotations

import os
import subprocess

# CREATE_NO_WINDOW is Windows-only; defined here so the value stays assertable on any platform.
NO_WINDOW_FLAG = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _console_window_handle() -> int:
    """Return this process's console window handle (0 when it has none)."""
    if os.name != "nt":
        return 0
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetConsoleWindow.restype = ctypes.c_void_p
    return int(kernel32.GetConsoleWindow() or 0)


def child_creation_flags() -> int:
    """Return creation flags that keep a child process's console invisible.

    A console-less parent (pythonw.exe, DETACHED_PROCESS) otherwise makes Windows
    allocate a fresh, focus-stealing console for every child it spawns. The flags
    stay 0 whenever this process already owns a console window, so interactive
    runs keep their output and Ctrl+C delivery unchanged.
    """
    if os.name != "nt" or _console_window_handle():
        return 0
    return NO_WINDOW_FLAG
