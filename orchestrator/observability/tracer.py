"""OpenTelemetry distributed tracing and latency timeline collection."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider

    # Initialize SDK TracerProvider if not already set
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        resource = Resource.create({"service.name": "hina-orchestrator"})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
    _HAS_OTEL = True
except Exception:
    _HAS_OTEL = False


@dataclass
class StageTiming:
    stage: str
    duration_ms: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceRecord:
    trace_id: str
    session_id: str
    operation: str
    start_time: str
    total_duration_ms: float = 0.0
    stages: list[StageTiming] = field(default_factory=list)
    status: str = "success"
    error: str | None = None


class TraceManager:
    """Collects distributed trace records and stage timings for developer inspection."""

    def __init__(self, max_records: int = 200) -> None:
        self.max_records = max_records
        self._traces: dict[str, TraceRecord] = {}
        self._order: list[str] = []

    def start_trace(
        self, session_id: str, operation: str, trace_id: str | None = None
    ) -> TraceRecord:
        t_id = trace_id or str(uuid4())
        rec = TraceRecord(
            trace_id=t_id,
            session_id=session_id,
            operation=operation,
            start_time=datetime.now(UTC).isoformat(),
        )
        self._traces[t_id] = rec
        self._order.append(t_id)

        # Evict old traces if capacity exceeded
        if len(self._order) > self.max_records:
            oldest = self._order.pop(0)
            self._traces.pop(oldest, None)

        return rec

    def record_stage(
        self,
        trace_id: str,
        stage: str,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        rec = self._traces.get(trace_id)
        if rec:
            rec.stages.append(
                StageTiming(
                    stage=stage,
                    duration_ms=round(duration_ms, 2),
                    timestamp=datetime.now(UTC).isoformat(),
                    metadata=metadata or {},
                )
            )
            rec.total_duration_ms = round(sum(s.duration_ms for s in rec.stages), 2)

    def finish_trace(
        self, trace_id: str, status: str = "success", error: str | None = None
    ) -> None:
        rec = self._traces.get(trace_id)
        if rec:
            rec.status = status
            rec.error = error

    def get_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        recent_ids = list(reversed(self._order))[:limit]
        out: list[dict[str, Any]] = []
        for tid in recent_ids:
            rec = self._traces.get(tid)
            if rec:
                out.append(
                    {
                        "trace_id": rec.trace_id,
                        "session_id": rec.session_id,
                        "operation": rec.operation,
                        "start_time": rec.start_time,
                        "total_duration_ms": rec.total_duration_ms,
                        "status": rec.status,
                        "error": rec.error,
                        "stages": [
                            {
                                "stage": s.stage,
                                "duration_ms": s.duration_ms,
                                "timestamp": s.timestamp,
                                "metadata": s.metadata,
                            }
                            for s in rec.stages
                        ],
                    }
                )
        return out

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        rec = self._traces.get(trace_id)
        if not rec:
            return None
        return {
            "trace_id": rec.trace_id,
            "session_id": rec.session_id,
            "operation": rec.operation,
            "start_time": rec.start_time,
            "total_duration_ms": rec.total_duration_ms,
            "status": rec.status,
            "error": rec.error,
            "stages": [
                {
                    "stage": s.stage,
                    "duration_ms": s.duration_ms,
                    "timestamp": s.timestamp,
                    "metadata": s.metadata,
                }
                for s in rec.stages
            ],
        }


# Global trace collector singleton
trace_manager = TraceManager()
