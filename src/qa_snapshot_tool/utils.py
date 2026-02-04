import sys
from pathlib import Path

def get_app_root() -> Path:
    """Returns the application root directory (repo root in dev, _MEIPASS in frozen)."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]
