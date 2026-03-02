"""Application settings persisted under the user profile."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class AppSettings:
    session_store_root: str = str(Path.home() / ".qa_snapshot_tool" / "sessions")
    session_max_bytes: int = 15 * 1024 * 1024 * 1024
    max_concurrent_devices: int = 3
    emulator_beta_enabled: bool = False
    maestro_workspace_path: str = ""
    auto_record_live: bool = True

    @staticmethod
    def config_path() -> Path:
        base = Path.home() / ".qa_snapshot_tool"
        base.mkdir(parents=True, exist_ok=True)
        return base / "config.json"

    @staticmethod
    def _sanitize(raw: Dict[str, Any]) -> "AppSettings":
        defaults = AppSettings()
        merged = asdict(defaults)
        merged.update(raw or {})
        merged["session_store_root"] = str(Path(merged["session_store_root"]))
        merged["session_max_bytes"] = max(1024 * 1024 * 1024, int(merged["session_max_bytes"]))
        merged["max_concurrent_devices"] = max(1, min(3, int(merged["max_concurrent_devices"])))
        merged["emulator_beta_enabled"] = bool(merged["emulator_beta_enabled"])
        merged["maestro_workspace_path"] = str(merged["maestro_workspace_path"] or "")
        merged["auto_record_live"] = bool(merged["auto_record_live"])
        return AppSettings(**merged)

    @classmethod
    def load(cls) -> "AppSettings":
        path = cls.config_path()
        if not path.exists():
            settings = cls()
            settings.save()
            return settings
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return cls._sanitize(data)
        except Exception:
            settings = cls()
            settings.save()
            return settings

    def save(self) -> None:
        path = self.config_path()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2)

    def session_root_path(self) -> Path:
        path = Path(self.session_store_root)
        path.mkdir(parents=True, exist_ok=True)
        return path
