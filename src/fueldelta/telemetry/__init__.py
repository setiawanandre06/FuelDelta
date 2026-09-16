"""Source contracts and adapters; no Assetto Corsa integration yet."""

from .source import TelemetrySource
from .fake import FakeTelemetrySource

__all__ = ["TelemetrySource", "FakeTelemetrySource"]
