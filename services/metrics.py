"""Application metrics — in-memory counters for Prometheus-style export.

For production, use the prometheus_client library. This provides a lightweight
alternative for development that follows the same patterns.
"""

import time
from collections import defaultdict
from typing import Any


class Metrics:
    """Simple in-memory metrics collector."""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = defaultdict(float)

    def increment(self, name: str, labels: dict[str, str] | None = None, amount: int = 1):
        key = self._make_key(name, labels)
        self._counters[key] += amount

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None):
        key = self._make_key(name, labels)
        self._histograms[key].append(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None):
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int:
        key = self._make_key(name, labels)
        return self._counters[key]

    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict:
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0}
        values.sort()
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "p50": values[len(values) // 2],
            "p95": values[int(len(values) * 0.95)] if len(values) > 1 else values[0],
            "p99": values[int(len(values) * 0.99)] if len(values) > 1 else values[0],
        }

    def export(self) -> dict[str, Any]:
        """Export all metrics as a dict."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k) for k in self._histograms
            },
        }

    @staticmethod
    def _make_key(name: str, labels: dict[str, str] | None = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Singleton
metrics = Metrics()


class Timer:
    """Context manager for timing operations."""

    def __init__(self, metric_name: str, labels: dict[str, str] | None = None):
        self.metric_name = metric_name
        self.labels = labels
        self._start: float = 0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        duration = time.monotonic() - self._start
        metrics.observe(self.metric_name, duration, self.labels)
