"""Source contracts and adapters; importing does not connect to the game."""

from .source import TelemetrySource
from .fake import FakeTelemetrySource
from .assetto_corsa import AssettoCorsaTelemetrySource
from .ac_memory import TelemetryUnavailable
from .recording import SessionRecorder
from .replay import ReplayTelemetrySource

__all__ = ["TelemetrySource", "FakeTelemetrySource", "AssettoCorsaTelemetrySource",
           "TelemetryUnavailable", "SessionRecorder", "ReplayTelemetrySource"]
