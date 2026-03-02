from dataclasses import dataclass
from typing import List, Tuple

from PySide6.QtGui import QColor, QImage

from qa_snapshot_tool.gui import DeviceWorkspace, MainWindow


class _FakeVideo:
    def __init__(self):
        self.values: List[int] = []

    def set_target_fps(self, fps: int) -> None:
        self.values.append(int(fps))


class _FakeXml:
    def __init__(self):
        self.values: List[float] = []

    def set_poll_interval(self, seconds: float) -> None:
        self.values.append(float(seconds))


class _FakeFocus:
    def __init__(self):
        self.values: List[float] = []

    def set_poll_interval(self, seconds: float) -> None:
        self.values.append(float(seconds))


class _FakeLog:
    def __init__(self):
        self.values: List[int] = []

    def set_emit_every_n(self, n: int) -> None:
        self.values.append(int(n))


class _FakeRecorder:
    def __init__(self):
        self.events: List[Tuple[str, dict]] = []
        self.frames: List[str] = []
        self.xmls: List[str] = []

    def record_event(self, kind: str, payload: dict) -> None:
        self.events.append((kind, payload))

    def record_frame(self, image: QImage, reason: str = "periodic"):
        self.frames.append(reason)
        return None

    def record_xml_dump(self, xml: str, reason: str = "changed"):
        self.xmls.append(reason)
        return None


def test_background_scheduler_applies_active_vs_background_policy():
    a = DeviceWorkspace(serial="A")
    b = DeviceWorkspace(serial="B")
    a.video_thread = _FakeVideo()
    b.video_thread = _FakeVideo()
    a.xml_thread = _FakeXml()
    b.xml_thread = _FakeXml()
    a.focus_thread = _FakeFocus()
    b.focus_thread = _FakeFocus()
    a.log_thread = _FakeLog()
    b.log_thread = _FakeLog()

    window = MainWindow.__new__(MainWindow)
    window.workspaces = {"A": a, "B": b}
    window.active_workspace_serial = "A"
    window.perf_mode = False

    MainWindow._apply_background_scheduler(window)

    assert a.video_thread.values[-1] == 8
    assert b.video_thread.values[-1] == 2
    assert a.xml_thread.values[-1] == 0.8
    assert b.xml_thread.values[-1] == 2.4
    assert a.focus_thread.values[-1] == 1.0
    assert b.focus_thread.values[-1] == 2.5
    assert a.log_thread.values[-1] == 1
    assert b.log_thread.values[-1] == 3


def test_event_capture_records_frame_and_xml_when_available():
    ws = DeviceWorkspace(serial="A")
    ws.recorder = _FakeRecorder()
    ws.last_xml = "<hierarchy/>"
    ws.last_frame_image = QImage(16, 16, QImage.Format_ARGB32)
    ws.last_frame_image.fill(QColor("#123456"))

    window = MainWindow.__new__(MainWindow)
    window.active_workspace_serial = "A"
    window.last_frame_image = None

    MainWindow._record_event_capture(window, ws, "dump_error", {"message": "x"}, include_xml=True)

    assert ws.recorder.events == [("dump_error", {"message": "x"})]
    assert ws.recorder.frames == ["event_dump_error"]
    assert ws.recorder.xmls == ["event_dump_error"]
