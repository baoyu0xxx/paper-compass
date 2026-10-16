from paper_compass import console_window


def test_no_flags_outside_windows(monkeypatch):
    monkeypatch.setattr(console_window.os, "name", "posix")
    assert console_window.child_creation_flags() == 0


def test_no_flags_when_a_console_window_is_attached(monkeypatch):
    monkeypatch.setattr(console_window.os, "name", "nt")
    monkeypatch.setattr(console_window, "_console_window_handle", lambda: 0x00010A2C)
    assert console_window.child_creation_flags() == 0


def test_console_less_process_hides_child_consoles(monkeypatch):
    monkeypatch.setattr(console_window.os, "name", "nt")
    monkeypatch.setattr(console_window, "_console_window_handle", lambda: 0)
    assert console_window.child_creation_flags() == console_window.NO_WINDOW_FLAG == 0x08000000


def test_console_window_probe_reports_none_without_a_console():
    # The test runner may or may not own a console window; the probe must simply
    # agree with the platform, never raise.
    assert console_window._console_window_handle() >= 0
