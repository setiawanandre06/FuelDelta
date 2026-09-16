"""Deterministic in-memory telemetry for development and tests."""

from fueldelta.models import TelemetrySample
from .source import TelemetrySource


def _demo_samples():
    # type: () -> tuple
    """Return fresh synthetic observations; not a vehicle physics model."""
    return (
        TelemetrySample(0.0, 30.0, 100.0, 0.8, 0.0, 4500, 3, 1, 0, 0.0),
        TelemetrySample(1.0, 29.99, 105.0, 0.5, 0.0, 4700, 3, 1, 1000, 0.01),
        TelemetrySample(2.0, 29.985, 102.0, 0.0, 0.1, 4500, 3, 1, 2000, 0.02),
    )


class FakeTelemetrySource(TelemetrySource):
    """Read a supplied iterable of samples once, in order.

    With no argument, use three synthetic demo observations. An explicitly
    empty iterable stays empty. No sleeping, clock access, or game is needed.
    Samples are returned as supplied; each source owns its iterator position.
    """

    def __init__(self, samples=None):
        self._samples = iter(_demo_samples() if samples is None else samples)

    def read(self):
        # type: () -> TelemetrySample
        sample = next(self._samples)
        if not isinstance(sample, TelemetrySample):
            raise TypeError("Expected a TelemetrySample")
        return sample
