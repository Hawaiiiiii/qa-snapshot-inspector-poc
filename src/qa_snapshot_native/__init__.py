"""Native hotspot facade with Python fallbacks.

This module exposes a stable API used by QUANTUM 2.0 performance paths.
If a compiled backend exists, it is used automatically. Otherwise, Python
implementations are used.
"""

from __future__ import annotations

import hashlib
import zlib
from typing import Any, Iterable, Optional, Sequence, Tuple

RectNode = Tuple[Tuple[int, int, int, int], Any]

_BACKEND_NAME = "python"

try:
    # Optional compiled extension (not required).
    from . import _native  # type: ignore

    _BACKEND_NAME = "native"
except Exception:
    _native = None


def backend_name() -> str:
    return _BACKEND_NAME


def has_native_backend() -> bool:
    return _native is not None


def frame_sha1(data: bytes) -> str:
    if _native and hasattr(_native, "frame_sha1"):
        return str(_native.frame_sha1(data))
    return hashlib.sha1(data).hexdigest()


def compress_payload(data: bytes, level: int = 6) -> bytes:
    if _native and hasattr(_native, "compress_payload"):
        return bytes(_native.compress_payload(data, int(level)))
    return zlib.compress(data, level=max(1, min(9, int(level))))


def smallest_hit(rect_nodes: Sequence[RectNode], x: int, y: int) -> Optional[Any]:
    if _native and hasattr(_native, "smallest_hit"):
        return _native.smallest_hit(rect_nodes, int(x), int(y))

    best_node: Optional[Any] = None
    best_area: Optional[int] = None
    for rect, node in rect_nodes:
        rx, ry, rw, rh = rect
        if rw <= 0 or rh <= 0:
            continue
        if rx <= x <= (rx + rw) and ry <= y <= (ry + rh):
            area = rw * rh
            if best_area is None or area < best_area:
                best_area = area
                best_node = node
    return best_node


def sort_rects_by_area(rect_nodes: Iterable[RectNode]) -> list[RectNode]:
    return sorted(rect_nodes, key=lambda item: (item[0][2] * item[0][3]))
