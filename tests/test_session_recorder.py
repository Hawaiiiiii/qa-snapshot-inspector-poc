import os
import sqlite3
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from qa_snapshot_tool.session_recorder import SessionRecorder, SessionRecorderRegistry


def _count_rows(db_path: Path, table: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    finally:
        con.close()


def test_recorder_periodic_dedupe_and_event_frame_capture(tmp_path: Path):
    recorder = SessionRecorder.start_session(
        session_root=tmp_path / "sessions",
        serial="ABC123",
        model="RackModel",
        environment_type="rack",
        profile="rack_aaos",
        display_id="0",
        session_max_bytes=1024 * 1024 * 1024,
    )

    img = QImage(32, 32, QImage.Format_ARGB32)
    img.fill(QColor("#335577"))

    first = recorder.record_frame(img, reason="periodic")
    skipped = recorder.record_frame(img, reason="periodic")
    event_frame = recorder.record_frame(img, reason="event_tap")

    recorder.finish_session("stopped")

    assert first is not None and first.exists()
    assert skipped is None
    assert event_frame is not None and event_frame.exists()
    assert _count_rows(recorder.db_path, "frames") == 2


def test_recorder_xml_changed_dedupe_and_event_capture(tmp_path: Path):
    recorder = SessionRecorder.start_session(
        session_root=tmp_path / "sessions",
        serial="ABC999",
        model="RackModel",
        environment_type="rack",
        profile="rack_aaos",
        display_id="0",
        session_max_bytes=1024 * 1024 * 1024,
    )

    xml = '<hierarchy><node class="android.widget.TextView" bounds="[0,0][10,10]"/></hierarchy>'
    first = recorder.record_xml_dump(xml, reason="changed")
    second = recorder.record_xml_dump(xml, reason="changed")
    event_xml = recorder.record_xml_dump(xml, reason="event_dump_error")

    recorder.finish_session("stopped")

    assert first is not None and first.exists()
    assert second is None
    assert event_xml is not None and event_xml.exists()
    assert _count_rows(recorder.db_path, "xml_dumps") == 2


def test_recorder_global_crash_keeps_pre_crash_artifacts(tmp_path: Path):
    recorder = SessionRecorder.start_session(
        session_root=tmp_path / "sessions",
        serial="CRASH01",
        model="RackModel",
        environment_type="rack",
        profile="rack_aaos",
        display_id=None,
        session_max_bytes=1024 * 1024 * 1024,
    )

    img = QImage(24, 24, QImage.Format_ARGB32)
    img.fill(QColor("#112233"))
    recorder.record_frame(img, reason="event_pre_crash")
    recorder.record_xml_dump('<hierarchy><node class="x" bounds="[0,0][5,5]"/></hierarchy>', reason="event_pre_crash")
    recorder.record_log_line("pre-crash log")

    SessionRecorderRegistry.record_global_crash("boom")
    recorder.finish_session("crashed")

    crash_files = list(recorder.session_dir.glob("crash_*.txt"))
    assert crash_files
    assert _count_rows(recorder.db_path, "events") >= 3


def test_recorder_prunes_oldest_sessions_deterministically(tmp_path: Path):
    session_root = tmp_path / "sessions"
    old_a = session_root / "20240101_000001_old_a"
    old_b = session_root / "20240101_000002_old_b"
    old_a.mkdir(parents=True, exist_ok=True)
    old_b.mkdir(parents=True, exist_ok=True)
    (old_a / "blob.bin").write_bytes(b"a" * 700_000)
    (old_b / "blob.bin").write_bytes(b"b" * 700_000)
    os.utime(old_a, (1, 1))
    os.utime(old_b, (2, 2))

    recorder = SessionRecorder.start_session(
        session_root=session_root,
        serial="PRUNE01",
        model="RackModel",
        environment_type="rack",
        profile="rack_aaos",
        display_id=None,
        session_max_bytes=1_000_000,
    )
    recorder.finish_session("stopped")

    assert not old_a.exists()
    assert old_b.exists()
    assert recorder.session_dir.exists()
