"""Metrics collection — Prometheus-compatible metrics for monitoring."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cloakbrowser.manager.metrics")


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    _instance: MetricsCollector | None = None

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._start_time: float = time.monotonic()

    @classmethod
    def get(cls) -> MetricsCollector:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def record_workflow_duration(self, duration_seconds: float, execution_path: str, workflow_id: str) -> None:
        self.observe_histogram(
            "cloakbrowser_workflow_duration_seconds",
            duration_seconds,
            {"execution_path": execution_path, "workflow_id": workflow_id},
        )

    def record_llm_tokens(self, tokens: int, model: str, execution_path: str) -> None:
        self.inc_counter(
            "cloakbrowser_workflow_llm_tokens_total",
            float(tokens),
            {"model": model, "execution_path": execution_path},
        )

    def set_browser_pool_active(self, count: int) -> None:
        self.set_gauge("cloakbrowser_browser_pool_active", float(count))

    def set_browser_pool_waiting(self, count: int) -> None:
        self.set_gauge("cloakbrowser_browser_pool_waiting", float(count))

    def set_script_cache_hit_rate(self, rate: float) -> None:
        self.set_gauge("cloakbrowser_script_cache_hit_rate", rate)

    def set_workflow_success_rate(self, rate: float, execution_path: str) -> None:
        self.set_gauge(
            "cloakbrowser_workflow_success_rate",
            rate,
            {"execution_path": execution_path},
        )

    def get_prometheus_output(self) -> str:
        lines: list[str] = []
        lines.append(f"# CloakBrowser Manager Metrics")
        lines.append(f"# Uptime: {time.monotonic() - self._start_time:.0f}s")
        lines.append("")

        for key, value in sorted(self._counters.items()):
            name, labels = self._parse_key(key)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{self._format_labels(labels)} {value}")
        lines.append("")

        for key, value in sorted(self._gauges.items()):
            name, labels = self._parse_key(key)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{self._format_labels(labels)} {value}")
        lines.append("")

        for key, values in sorted(self._histograms.items()):
            name, labels = self._parse_key(key)
            lines.append(f"# TYPE {name} histogram")
            count = len(values)
            total = sum(values)
            avg = total / count if count > 0 else 0
            lines.append(f"{name}_count{self._format_labels(labels)} {count}")
            lines.append(f"{name}_sum{self._format_labels(labels)} {total:.4f}")
            lines.append(f"{name}_avg{self._format_labels(labels)} {avg:.4f}")
        lines.append("")

        return "\n".join(lines)

    def get_json(self) -> dict[str, Any]:
        return {
            "counters": {k: v for k, v in sorted(self._counters.items())},
            "gauges": {k: v for k, v in sorted(self._gauges.items())},
            "histograms": {
                k: {"count": len(v), "sum": sum(v), "avg": sum(v) / len(v) if v else 0}
                for k, v in sorted(self._histograms.items())
            },
            "uptime_seconds": time.monotonic() - self._start_time,
        }

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _parse_key(self, key: str) -> tuple[str, dict[str, str]]:
        if "{" not in key:
            return key, {}
        name = key[: key.index("{")]
        label_str = key[key.index("{") + 1 : key.index("}")]
        labels = {}
        for part in label_str.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                labels[k] = v.strip('"')
        return name, labels

    def _format_labels(self, labels: dict[str, str]) -> str:
        if not labels:
            return ""
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{{{label_str}}}"
