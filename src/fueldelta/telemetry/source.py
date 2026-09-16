"""Telemetry source contract compatible with Python 3.3.5."""

from abc import ABCMeta, abstractmethod

from fueldelta.models import TelemetrySample


class TelemetrySource(object, metaclass=ABCMeta):
    """ABC equivalent of a read protocol for the legacy Python runtime.

    Consumers only need read(); inheritance is optional for duck-typed
    implementations. Finite sources raise StopIteration when exhausted.
    Each source must return values normalized to TelemetrySample conventions.
    """

    @abstractmethod
    def read(self):
        # type: () -> TelemetrySample
        """Return the next sample, or raise StopIteration at end of data."""
        raise NotImplementedError
