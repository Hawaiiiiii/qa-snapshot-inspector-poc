from typing import List

from PySide6.QtGui import QColor, QImage

from qa_snapshot_tool.gui import DeviceWorkspace, MainWindow


class _Perf:
    def __init__(self):
        self.samples = []

    def record(self, name: str, duration_ms: float) -> None:
        self.samples.append((name, float(duration_ms)))


class _Text:
    def __init__(self):
        self.lines: List[str] = []

    def append(self, text: str) -> None:
        self.lines.append(text)


def test_workspace_log_tree_frame_updates_are_isolated_by_serial():
    ws_a = DeviceWorkspace(serial="A")
    ws_b = DeviceWorkspace(serial="B")

    window = MainWindow.__new__(MainWindow)
    window.workspaces = {"A": ws_a, "B": ws_b}
    window.active_workspace_serial = "A"
    window.perf = _Perf()
    window.txt_log = _Text()
    window.stream_scale = 1.0
    window.dump_bounds = None
    window.device_bounds = None

    tree_calls: List[tuple] = []
    frame_calls: List[int] = []
    window.on_tree_data = lambda xml, changed: tree_calls.append((xml, changed))
    window.on_frame = lambda image: frame_calls.append(image.width())

    # Background workspace log should not write to active log widget.
    MainWindow.on_workspace_log_line(window, "B", "bg-line", source="logcat")
    assert ws_b.log_lines[-1] == "bg-line"
    assert ws_a.log_lines == []
    assert window.txt_log.lines == []

    # Background workspace tree should not trigger active tree rendering.
    MainWindow.on_workspace_tree(window, "B", "<hierarchy/>", True)
    assert ws_b.last_xml == "<hierarchy/>"
    assert tree_calls == []

    # Background workspace frame should be cached only in that workspace.
    bg_img = QImage(20, 20, QImage.Format_ARGB32)
    bg_img.fill(QColor("#778899"))
    MainWindow.on_workspace_frame(window, "B", bg_img)
    assert ws_b.last_frame_image is not None
    assert ws_a.last_frame_image is None
    assert frame_calls == []

    # Active workspace routes to active rendering callbacks.
    active_img = QImage(30, 30, QImage.Format_ARGB32)
    active_img.fill(QColor("#112233"))
    MainWindow.on_workspace_frame(window, "A", active_img)
    assert frame_calls[-1] == 30
