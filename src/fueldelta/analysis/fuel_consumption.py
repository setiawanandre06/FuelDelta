"""Fuel consumption from normalized telemetry, independent of its source."""

import math

from fueldelta.models import TelemetrySample


def _nonnegative_number(value):
    # type: (object) -> bool
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


class FuelConsumptionAnalyzer(object):
    """Track accepted lap consumption in liters for the current session.

    Missing data or gaps longer than max_sample_gap_seconds discard the
    affected interval. Boundary fuel is the first observation of the next
    lap, so accuracy depends on telemetry sampling frequency.
    """

    def __init__(self, max_sample_gap_seconds=2.0):
        # type: (float) -> None
        if not _nonnegative_number(max_sample_gap_seconds) or max_sample_gap_seconds == 0:
            raise ValueError("max_sample_gap_seconds must be positive and finite")
        self.max_sample_gap_seconds = max_sample_gap_seconds
        self.reset_session()

    def reset_session(self):
        # type: () -> None
        """Clear history and pending lap; call on explicit session changes."""
        self._history = []  # type: list
        self._previous = None
        self._start_fuel = None
        self._lap_valid = False

    @property
    def consumption_history(self):
        # type: () -> tuple
        """Immutable snapshot of accepted laps, in completion order (liters)."""
        return tuple(self._history)

    @property
    def last_lap_consumption(self):
        # type: () -> object
        """Most recent accepted lap in liters, or None if none exists."""
        return self._history[-1] if self._history else None

    @property
    def average_consumption(self):
        # type: () -> object
        """Mean of all accepted laps this session, or None."""
        return self._mean(self._history)

    def rolling_average(self, n=5):
        # type: (int) -> object
        """Mean of the last n accepted laps (or those available), or None."""
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("n must be a positive integer")
        return self._mean(self._history[-n:])

    @staticmethod
    def _mean(values):
        # type: (list) -> object
        return math.fsum(values) / len(values) if values else None

    def record_lap(self, start_fuel_liters, end_fuel_liters,
                   valid=True, refueled=False):
        # type: (float, float, bool, bool) -> object
        """Record a complete lap; return liters used, or None if rejected.

        Manual callers must know the full lap was observed, report invalid
        laps and any refueling (even when net fuel decreased). Endpoints
        alone cannot reveal fuel added and then consumed within a lap.
        This method does not change the pending telemetry lap.
        """
        if (not valid or refueled
                or not _nonnegative_number(start_fuel_liters)
                or not _nonnegative_number(end_fuel_liters)
                or end_fuel_liters > start_fuel_liters):
            return None
        consumption = start_fuel_liters - end_fuel_liters
        self._history.append(consumption)
        return consumption

    def invalidate_current_lap(self):
        # type: () -> None
        """Invalidate the pending lap, for example after an external penalty."""
        self._lap_valid = False

    def update(self, sample, lap_valid=True):
        # type: (object, bool) -> object
        """Consume a TelemetrySample or None; return completed liters or None.

        lap_valid applies to the lap named by sample, including on a boundary.
        Once invalid, a lap remains invalid. Pass None for missing telemetry.
        Timestamp/lap-number rollback starts a new session; equal timestamps
        are treated as missing data, since their ordering is ambiguous.
        """
        if sample is not None and not isinstance(sample, TelemetrySample):
            raise TypeError("Expected a TelemetrySample or None")
        if sample is None or not self._usable(sample):
            self.invalidate_current_lap()
            self._start_fuel = None
            return None

        previous = self._previous
        if previous is not None:
            old_time, old_lap, old_fuel = previous
            if sample.timestamp < old_time or sample.lap_number < old_lap:
                self.reset_session()
                previous = None

        if previous is None:
            # A mid-lap first observation cannot measure a complete lap.
            self._begin_lap(sample, lap_valid and sample.lap_time_ms == 0)
            return None

        elapsed = sample.timestamp - previous[0]
        uninterrupted = 0 < elapsed <= self.max_sample_gap_seconds
        refueled = sample.fuel_liters > previous[2]
        if not uninterrupted or refueled:
            self.invalidate_current_lap()

        result = None
        if sample.lap_number != previous[1]:
            if sample.lap_number == previous[1] + 1:
                result = self.record_lap(
                    self._start_fuel, sample.fuel_liters,
                    valid=self._lap_valid, refueled=refueled)
            # After a gap, only an exact lap-start sample is a safe baseline.
            boundary_known = (uninterrupted and self._start_fuel is not None
                              and sample.lap_number == previous[1] + 1)
            self._begin_lap(sample, lap_valid and
                            (boundary_known or sample.lap_time_ms == 0))
        else:
            self._lap_valid = self._lap_valid and lap_valid
            self._remember(sample)
        return result

    @staticmethod
    def _usable(sample):
        # type: (TelemetrySample) -> bool
        return (_nonnegative_number(sample.timestamp)
                and _nonnegative_number(sample.fuel_liters)
                and isinstance(sample.lap_number, int)
                and not isinstance(sample.lap_number, bool)
                and sample.lap_number >= 1
                and isinstance(sample.lap_time_ms, int)
                and not isinstance(sample.lap_time_ms, bool)
                and sample.lap_time_ms >= 0)

    def _begin_lap(self, sample, valid):
        # type: (TelemetrySample, bool) -> None
        self._start_fuel = sample.fuel_liters
        self._lap_valid = valid
        self._remember(sample)

    def _remember(self, sample):
        # type: (TelemetrySample) -> None
        # Copy primitives so subsequent mutation by a source cannot alter state.
        self._previous = (sample.timestamp, sample.lap_number, sample.fuel_liters)
