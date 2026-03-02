"""Continuous live session recorder with timeline index and crash-safe retention."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from qa_snapshot_native import compress_payload, frame_sha1

@dataclass
class SessionContext:
    session_id: str
    serial: str
    model: str
    environment_type: str
    profile: str
    start_ts: float
    display_id: Optional[str]


class SessionRecorderRegistry:
    _lock = threading.Lock()
    _active: Dict[str, "SessionRecorder"] = {}

    @classmethod
    def register(cls, serial: str, recorder: "SessionRecorder") -> None:
        with cls._lock:
            cls._active[serial] = recorder

    @classmethod
    def unregister(cls, serial: str) -> None:
        with cls._lock:
            cls._active.pop(serial, None)

    @classmethod
    def record_global_crash(cls, crash_text: str) -> None:
        with cls._lock:
            recorders = list(cls._active.values())
        for recorder in recorders:
            try:
                recorder.record_crash(crash_text)
            except Exception:
                continue


class SessionRecorder:
    def __init__(
        self,
        root: Path,
        context: SessionContext,
        session_max_bytes: int,
    ) -> None:
        self.root = root
        self.context = context
        self.session_max_bytes = int(session_max_bytes)

        self.session_dir = self.root / self.context.session_id
        self.frames_dir = self.session_dir / "frames"
        self.xml_dir = self.session_dir / "xml"
        self.bookmarks_dir = self.session_dir / "bookmarks"
        self.export_dir = self.session_dir / "exports"

        for path in (self.session_dir, self.frames_dir, self.xml_dir, self.bookmarks_dir, self.export_dir):
            path.mkdir(parents=True, exist_ok=True)

        self.log_path = self.session_dir / "logcat_live.txt"
        self.meta_path = self.session_dir / "meta.json"
        self.db_path = self.session_dir / "session.db"

        self._last_frame_ts = 0.0
        self._last_frame_hash = ""
        self._last_xml_hash = ""
        self._last_xml_path: Optional[Path] = None
        self._last_frame_path: Optional[Path] = None
        self._finished = False
        self._lock = threading.Lock()

        self._db = sqlite3.connect(str(self.db_path))
        self._db.execute("PRAGMA journal_mode=WAL;")
        self._db.execute("PRAGMA synchronous=NORMAL;")
        self._create_schema()

        self._write_meta(extra={"status": "running"})
        self.record_event("session_started", {
            "serial": self.context.serial,
            "model": self.context.model,
            "environment_type": self.context.environment_type,
            "profile": self.context.profile,
            "display_id": self.context.display_id,
        })

    @classmethod
    def start_session(
        cls,
        session_root: Path,
        serial: str,
        model: str,
        environment_type: str,
        profile: str,
        display_id: Optional[str],
        session_max_bytes: int,
    ) -> "SessionRecorder":
        session_root.mkdir(parents=True, exist_ok=True)
        session_id = time.strftime("%Y%m%d_%H%M%S") + f"_{serial.replace(':', '_')}"
        context = SessionContext(
            session_id=session_id,
            serial=serial,
            model=model,
            environment_type=environment_type,
            profile=profile,
            start_ts=time.time(),
            display_id=display_id,
        )
        recorder = cls(session_root, context, session_max_bytes=session_max_bytes)
        SessionRecorderRegistry.register(serial, recorder)
        recorder._enforce_rolling_cap()
        return recorder

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                file_relpath TEXT
            );

            CREATE TABLE IF NOT EXISTS frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                reason TEXT NOT NULL,
                file_relpath TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                sha1 TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS xml_dumps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                reason TEXT NOT NULL,
                file_relpath TEXT NOT NULL,
                md5 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def _write_meta(self, extra: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {
            "session_id": self.context.session_id,
            "serial": self.context.serial,
            "model": self.context.model,
            "environment_type": self.context.environment_type,
            "profile": self.context.profile,
            "display_id": self.context.display_id,
            "start_ts": self.context.start_ts,
            "start_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.context.start_ts)),
        }
        if extra:
            payload.update(extra)
        with self.meta_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _to_png_bytes(self, image: QImage) -> bytes:
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        qbytes: QByteArray = buffer.data()
        return bytes(qbytes)

    def record_frame(self, image: QImage, reason: str = "periodic") -> Optional[Path]:
        if image.isNull() or self._finished:
            return None

        now = time.time()
        png = self._to_png_bytes(image)
        digest = frame_sha1(png)

        # Adaptive timeline: periodic samples are throttled and deduplicated.
        if reason == "periodic":
            if (now - self._last_frame_ts) < 1.0:
                return None
            if digest == self._last_frame_hash and (now - self._last_frame_ts) < 2.5:
                return None

        rel = Path("frames") / f"{int(now * 1000)}_{reason}.png"
        out = self.session_dir / rel
        out.write_bytes(png)

        with self._lock:
            self._db.execute(
                "INSERT INTO frames(ts, reason, file_relpath, width, height, sha1) VALUES (?, ?, ?, ?, ?, ?)",
                (now, reason, str(rel).replace("\\", "/"), image.width(), image.height(), digest),
            )
            self._db.execute(
                "INSERT INTO events(ts, kind, payload_json, file_relpath) VALUES (?, ?, ?, ?)",
                (now, "frame", json.dumps({"reason": reason}), str(rel).replace("\\", "/")),
            )
            self._db.commit()

        self._last_frame_ts = now
        self._last_frame_hash = digest
        self._last_frame_path = out
        return out

    def record_xml_dump(self, xml: str, reason: str = "changed") -> Optional[Path]:
        if self._finished or not xml:
            return None
        now = time.time()
        digest = hashlib.md5(xml.encode("utf-8", errors="replace")).hexdigest()
        if reason == "changed" and digest == self._last_xml_hash:
            return None

        rel = Path("xml") / f"{int(now * 1000)}_{reason}.uix"
        out = self.session_dir / rel
        out.write_text(xml, encoding="utf-8", errors="replace")
        if out.stat().st_size > 512 * 1024:
            try:
                compressed = compress_payload(xml.encode("utf-8", errors="replace"))
                (out.with_suffix(".uix.z")).write_bytes(compressed)
            except Exception:
                pass

        with self._lock:
            self._db.execute(
                "INSERT INTO xml_dumps(ts, reason, file_relpath, md5, size_bytes) VALUES (?, ?, ?, ?, ?)",
                (now, reason, str(rel).replace("\\", "/"), digest, out.stat().st_size),
            )
            self._db.execute(
                "INSERT INTO events(ts, kind, payload_json, file_relpath) VALUES (?, ?, ?, ?)",
                (now, "xml_dump", json.dumps({"reason": reason}), str(rel).replace("\\", "/")),
            )
            self._db.commit()

        self._last_xml_hash = digest
        self._last_xml_path = out
        return out

    def record_log_line(self, message: str, source: str = "logcat") -> None:
        if self._finished:
            return
        now = time.time()
        line = f"[{time.strftime('%H:%M:%S', time.localtime(now))}] {message}\n"
        with self.log_path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(line)
        with self._lock:
            self._db.execute(
                "INSERT INTO logs(ts, source, message) VALUES (?, ?, ?)",
                (now, source, message),
            )
            self._db.commit()

    def record_event(self, kind: str, payload: Optional[Dict[str, Any]] = None, file_relpath: Optional[str] = None) -> None:
        if self._finished and kind != "session_finished":
            return
        with self._lock:
            self._db.execute(
                "INSERT INTO events(ts, kind, payload_json, file_relpath) VALUES (?, ?, ?, ?)",
                (time.time(), kind, json.dumps(payload or {}), file_relpath),
            )
            self._db.commit()

    def record_crash(self, crash_text: str) -> None:
        if self._finished:
            return
        crash_path = self.session_dir / f"crash_{int(time.time())}.txt"
        crash_path.write_text(crash_text, encoding="utf-8", errors="replace")
        self.record_event("crash", {"path": crash_path.name}, file_relpath=crash_path.name)

    def export_snapshot(self, destination_root: Optional[Path] = None, bookmark_label: str = "manual") -> Path:
        now = int(time.time())
        if destination_root is None:
            destination_root = self.bookmarks_dir
        destination_root.mkdir(parents=True, exist_ok=True)
        out = destination_root / f"snap_{now}"
        out.mkdir(parents=True, exist_ok=True)

        frame_src = self._last_frame_path
        xml_src = self._last_xml_path
        if frame_src and frame_src.exists():
            shutil.copy2(frame_src, out / "screenshot.png")
        if xml_src and xml_src.exists():
            shutil.copy2(xml_src, out / "dump.uix")
        if self.log_path.exists():
            shutil.copy2(self.log_path, out / "logcat.txt")

        meta = {
            "session_id": self.context.session_id,
            "serial": self.context.serial,
            "model": self.context.model,
            "environment_type": self.context.environment_type,
            "profile": self.context.profile,
            "display_id": self.context.display_id,
            "bookmark_label": bookmark_label,
            "exported_at": now,
        }
        with (out / "meta.json").open("w", encoding="utf-8") as handle:
            json.dump(meta, handle, indent=2)

        self.record_event("snapshot_bookmark", {
            "label": bookmark_label,
            "path": str(out),
        })
        return out

    def finish_session(self, status: str = "stopped") -> None:
        if self._finished:
            return
        self.record_event("session_finished", {"status": status})
        self._write_meta(extra={
            "status": status,
            "end_ts": time.time(),
        })
        self._finished = True
        try:
            self._db.close()
        finally:
            SessionRecorderRegistry.unregister(self.context.serial)
            self._enforce_rolling_cap()

    def _enforce_rolling_cap(self) -> None:
        if not self.root.exists():
            return

        dirs = [p for p in self.root.iterdir() if p.is_dir()]
        if not dirs:
            return

        def dir_size(path: Path) -> int:
            total = 0
            for node in path.rglob("*"):
                if node.is_file():
                    try:
                        total += node.stat().st_size
                    except OSError:
                        continue
            return total

        items = []
        total = 0
        for directory in dirs:
            size = dir_size(directory)
            ts = directory.stat().st_mtime
            items.append((ts, size, directory))
            total += size

        if total <= self.session_max_bytes:
            return

        items.sort(key=lambda item: item[0])
        for _, size, directory in items:
            if total <= self.session_max_bytes:
                break
            if directory == self.session_dir:
                continue
            shutil.rmtree(directory, ignore_errors=True)
            total -= size


def safe_capture_exception() -> str:
    return traceback.format_exc()
