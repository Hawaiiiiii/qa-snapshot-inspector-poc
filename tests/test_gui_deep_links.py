from pathlib import Path
import os

from qa_snapshot_tool.gui import MainWindow


class _Input:
    def __init__(self, value: str):
        self._value = value

    def text(self) -> str:
        return self._value


class _RowItem:
    def __init__(self, row: int):
        self._row = row

    def row(self) -> int:
        return self._row


class _Table:
    def __init__(self, row: int):
        self._row = row

    def selectedItems(self):
        return [_RowItem(self._row)]


def _window_for_test():
    window = MainWindow.__new__(MainWindow)
    logs = []
    window.log_sys = logs.append
    return window, logs


def test_open_last_handoff_folder_uses_manifest_parent(tmp_path: Path, monkeypatch):
    window, logs = _window_for_test()
    handoff_dir = tmp_path / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    manifest = handoff_dir / "quantum_handoff.json"
    manifest.write_text("{}", encoding="utf-8")
    window.last_handoff_manifest = str(manifest)

    opened = []

    def _fake_startfile(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr(os, "startfile", _fake_startfile, raising=False)
    MainWindow.open_last_handoff_folder(window)

    assert opened == [str(handoff_dir)]
    assert any("Opened handoff folder:" in line for line in logs)


def test_open_maestro_flows_opens_workspace_flows(tmp_path: Path, monkeypatch):
    window, logs = _window_for_test()
    workspace = tmp_path / "maestro_workspace"
    flows = workspace / "flows"
    flows.mkdir(parents=True, exist_ok=True)
    window.input_maestro_workspace = _Input(str(workspace))

    opened = []

    def _fake_startfile(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr(os, "startfile", _fake_startfile, raising=False)
    MainWindow.open_maestro_flows(window)

    assert opened == [str(flows)]
    assert any("Opened Maestro flows folder:" in line for line in logs)


def test_open_selected_timeline_session_opens_selected_dir(tmp_path: Path, monkeypatch):
    window, _ = _window_for_test()
    session_dir = tmp_path / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    window._selected_timeline_dir = lambda: session_dir

    opened = []

    def _fake_startfile(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr(os, "startfile", _fake_startfile, raising=False)
    MainWindow.open_selected_timeline_session(window)

    assert opened == [str(session_dir)]


def test_open_selected_timeline_file_opens_attached_path(tmp_path: Path, monkeypatch):
    window, _ = _window_for_test()
    target_file = tmp_path / "event.txt"
    target_file.write_text("ok", encoding="utf-8")
    window.tbl_timeline = _Table(row=0)
    window.timeline_event_file_paths = {0: str(target_file)}

    opened = []

    def _fake_startfile(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr(os, "startfile", _fake_startfile, raising=False)
    MainWindow.open_selected_timeline_file(window)

    assert opened == [str(target_file)]

