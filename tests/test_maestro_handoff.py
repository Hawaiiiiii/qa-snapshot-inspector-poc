import json
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from qa_snapshot_tool.maestro_handoff import export_session_handoff
from qa_snapshot_tool.session_recorder import SessionRecorder


def test_export_session_handoff_from_recorded_session(tmp_path: Path):
    session_root = tmp_path / "sessions"
    maestro_workspace = tmp_path / "maestro"

    recorder = SessionRecorder.start_session(
        session_root=session_root,
        serial="emulator-5554",
        model="Pixel_Emulator",
        environment_type="emulator",
        profile="android_studio_emulator",
        display_id=None,
        session_max_bytes=1024 * 1024 * 1024,
    )

    img = QImage(32, 32, QImage.Format_ARGB32)
    img.fill(QColor("#224466"))
    recorder.record_frame(img, reason="event")
    recorder.record_xml_dump('<hierarchy><node class="android.widget.TextView" bounds="[0,0][10,10]"/></hierarchy>')
    recorder.record_log_line("timeline log line")
    bookmark = recorder.export_snapshot(bookmark_label="unit-test")
    assert bookmark.exists()
    recorder.finish_session("stopped")

    result = export_session_handoff(
        session_dir=recorder.session_dir,
        maestro_workspace=maestro_workspace,
        locator_suggestions=[{"type": "Direct ID", "xpath": "//*[@resource-id='x']", "score": 10}],
    )
    export_dir = result["export_dir"]
    manifest_path = result["manifest_path"]

    assert export_dir.exists()
    assert manifest_path.exists()
    assert (export_dir / "session.db").exists()
    assert (export_dir / "meta.json").exists()
    assert (export_dir / "bookmarks").exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "quantum_handoff.v1"
    assert manifest["session_id"] == recorder.session_dir.name
    assert manifest["maestro_export_dir"] == str(export_dir)
    assert manifest["locator_suggestions"][0]["type"] == "Direct ID"


def test_export_session_handoff_skips_missing_optional_files(tmp_path: Path):
    session_dir = tmp_path / "sessions" / "manual_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "meta.json").write_text('{"serial":"ABC"}', encoding="utf-8")
    (session_dir / "session.db").write_bytes(b"")

    result = export_session_handoff(
        session_dir=session_dir,
        maestro_workspace=tmp_path / "maestro",
        locator_suggestions=[],
    )
    export_dir = result["export_dir"]
    assert (export_dir / "meta.json").exists()
    assert (export_dir / "session.db").exists()
    assert not (export_dir / "bookmarks").exists()
