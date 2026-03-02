"""Lightweight performance trackers for live telemetry."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict


@dataclass
class Metric:
    name: str
    alpha: float = 0.2
    history_size: int = 120
    avg_ms: float = 0.0
    count: int = 0
    samples: Deque[float] = field(default_factory=deque)

    def record(self, duration_ms: float) -> None:
        duration_ms = max(0.0, float(duration_ms))
        self.count += 1
        if self.count == 1:
            self.avg_ms = duration_ms
        else:
            self.avg_ms = (self.alpha * duration_ms) + ((1.0 - self.alpha) * self.avg_ms)
        self.samples.append(duration_ms)
        if len(self.samples) > self.history_size:
            self.samples.popleft()

    def p95_ms(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = int(round((len(ordered) - 1) * 0.95))
        return float(ordered[idx])


class PerfTracker:
    def __init__(self) -> None:
        self.metrics: Dict[str, Metric] = {
            "frame_decode": Metric("frame_decode"),
            "frame_render": Metric("frame_render"),
            "xml_parse": Metric("xml_parse"),
            "recorder_write": Metric("recorder_write"),
        }
        self.last_emit = 0.0

    def record(self, name: str, duration_ms: float) -> None:
        metric = self.metrics.get(name)
        if metric:
            metric.record(duration_ms)

    def summary(self) -> str:
        fdecode = self.metrics["frame_decode"]
        frender = self.metrics["frame_render"]
        xparse = self.metrics["xml_parse"]
        rwrite = self.metrics["recorder_write"]
        return (
            f"decode {fdecode.avg_ms:.1f}ms | "
            f"render {frender.avg_ms:.1f}ms | "
            f"xml {xparse.avg_ms:.1f}ms | "
            f"rec {rwrite.avg_ms:.1f}ms"
        )

    def should_emit(self, every_seconds: float = 5.0) -> bool:
        now = time.time()
        if (now - self.last_emit) >= every_seconds:
            self.last_emit = now
            return True
        return False
