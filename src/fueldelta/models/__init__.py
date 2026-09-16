"""Shared data models independent of telemetry access and UI."""

from .telemetry_sample import TelemetrySample
from .stint_projection import StintProjection

__all__ = ["TelemetrySample", "StintProjection"]
