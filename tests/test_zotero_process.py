from __future__ import annotations

import sys

import pytest

from paper_compass import zotero_process


def _platform(monkeypatch, platform):
    monkeypatch.setattr(zotero_process.sys, "platform", platform)


def test_zotero_running_matches_the_process_name(monkeypatch):
    _platform(monkeypatch, "win32")
    monkeypatch.setattr(zotero_process, "_process_names", lambda: {"chrome.exe", "Zotero.exe"})
    assert zotero_process.zotero_running() is True


def test_zotero_running_is_false_without_a_zotero_process(monkeypatch):
    _platform(monkeypatch, "win32")
    monkeypatch.setattr(zotero_process, "_process_names", lambda: {"chrome.exe", "python.exe"})
    assert zotero_process.zotero_running() is False


def test_zotero_running_degrades_to_false_when_enumeration_fails(monkeypatch):
    _platform(monkeypatch, "win32")

    def broken():
        raise OSError(5, "access denied")

    monkeypatch.setattr(zotero_process, "_win32_process_names", broken)
    assert zotero_process.zotero_running() is False


def test_zotero_running_is_unknown_off_windows(monkeypatch):
    _platform(monkeypatch, "linux")
    monkeypatch.setattr(zotero_process, "_process_names", lambda: {"zotero.exe"})
    assert zotero_process.zotero_running() is False


def test_process_enumeration_lists_the_current_interpreter():
    if sys.platform != "win32":
        pytest.skip("Win32 process enumeration only")
    names = zotero_process._win32_process_names()
    assert any(name.lower().startswith("python") for name in names)
