# src/prevent_outage_edge_testing/extractors/base.py
# Base classes for all extractors (metrics, logs, traces).

"""
Base extractor classes defining the interface for all data collectors.

Extractors can run in two modes:
- PRIVILEGED: Uses system-level tools (DTrace, eBPF, LD_PRELOAD)
- SIMULATOR: Safe fallback that generates synthetic data for testing logic
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from prevent_outage_edge_testing.models import ExtractorMode


class ExtractorStatus(str, Enum):
    """Current status of an extractor."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ExtractorResult(BaseModel):
    """Result from an extractor run."""

    extractor_id: str
    mode: ExtractorMode
    status: ExtractorStatus
    started_at: datetime
    ended_at: datetime | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T")


class BaseExtractor(ABC, Generic[T]):
    """
    Abstract base class for all extractors.

    Subclasses must implement both privileged and simulator modes.
    The extractor will automatically fall back to simulator mode
    if privileged mode is not available.
    """

    def __init__(
        self,
        extractor_id: str,
        mode: ExtractorMode = ExtractorMode.SIMULATOR,
    ) -> None:
        self.extractor_id = extractor_id
        self.mode = mode
        self.status = ExtractorStatus.IDLE
        self._started_at: datetime | None = None
        self._data: list[T] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this extractor."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this extractor collects."""
        ...

    @abstractmethod
    def _run_privileged(self) -> None:
        """Run the extractor in privileged mode (DTrace, eBPF, etc.)."""
        ...

    @abstractmethod
    def _run_simulator(self) -> None:
        """Run the extractor in simulator mode (safe fallback)."""
        ...

    @abstractmethod
    def _stop_privileged(self) -> None:
        """Stop privileged mode collection."""
        ...

    @abstractmethod
    def _stop_simulator(self) -> None:
        """Stop simulator mode collection."""
        ...

    def can_run_privileged(self) -> bool:
        """Check if privileged mode is available on this system."""
        return False  # Override in subclasses

    def start(self) -> None:
        """Start the extractor."""
        if self.status == ExtractorStatus.RUNNING:
            return

        self._started_at = datetime.utcnow()
        self._data = []
        self.status = ExtractorStatus.RUNNING

        try:
            if self.mode == ExtractorMode.PRIVILEGED:
                if self.can_run_privileged():
                    self._run_privileged()
                else:
                    # Fall back to simulator
                    self.mode = ExtractorMode.SIMULATOR
                    self._run_simulator()
            else:
                self._run_simulator()
        except Exception as e:
            self.status = ExtractorStatus.ERROR
            raise RuntimeError(f"Failed to start extractor: {e}") from e

    def stop(self) -> ExtractorResult:
        """Stop the extractor and return results."""
        ended_at = datetime.utcnow()

        try:
            if self.mode == ExtractorMode.PRIVILEGED:
                self._stop_privileged()
            else:
                self._stop_simulator()
            self.status = ExtractorStatus.STOPPED
            error = None
        except Exception as e:
            self.status = ExtractorStatus.ERROR
            error = str(e)

        return ExtractorResult(
            extractor_id=self.extractor_id,
            mode=self.mode,
            status=self.status,
            started_at=self._started_at or ended_at,
            ended_at=ended_at,
            data=[self._serialize_item(d) for d in self._data],
            error=error,
            metadata={"name": self.name, "description": self.description},
        )

    def _serialize_item(self, item: T) -> dict[str, Any]:
        """Serialize a data item to dict. Override for custom types."""
        if isinstance(item, BaseModel):
            return item.model_dump()
        if isinstance(item, dict):
            return item
        return {"value": item}

    def add_data(self, item: T) -> None:
        """Add a data item to the collection."""
        self._data.append(item)


class MetricSample(BaseModel):
    """A single metric sample."""

    name: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: dict[str, str] = Field(default_factory=dict)


class MetricExtractor(BaseExtractor[MetricSample]):
    """Base class for metric extractors."""

    @property
    def description(self) -> str:
        return "Collects numeric metrics from the system"


class LogEntry(BaseModel):
    """A single log entry."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = "INFO"
    message: str
    source: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class LogExtractor(BaseExtractor[LogEntry]):
    """Base class for log extractors."""

    @property
    def description(self) -> str:
        return "Collects log entries from the system"


class TraceSpan(BaseModel):
    """A single trace span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: datetime | None = None
    status: str = "OK"
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceExtractor(BaseExtractor[TraceSpan]):
    """Base class for trace extractors."""

    @property
    def description(self) -> str:
        return "Collects distributed trace spans"
