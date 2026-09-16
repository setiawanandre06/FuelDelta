"""Transparent lap-level pace/fuel comparisons, without statistical inference."""

import math

from fueldelta.models import LapPerformance, PaceFuelComparison


def _measurement(name, value, positive=False):
    # type: (str, object, bool) -> float
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be numeric")
    try:
        value = float(value)
    except OverflowError:
        raise ValueError(name + " exceeds numeric range")
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(name + " must be finite and " + ("positive" if positive else "nonnegative"))
    return value


class PaceFuelAnalyzer(object):
    """Store valid complete laps for one session and compare to a fixed baseline.

    The caller supplies paired lap duration and consumption from the same lap,
    and marks partial, invalid, missing-data, and refueling laps for exclusion.
    Baseline selection is explicit; no rolling baseline changes during analysis.
    """

    def __init__(self, baseline_lap_seconds, baseline_fuel_liters):
        # type: (float, float) -> None
        self.baseline_lap_seconds = _measurement("baseline_lap_seconds", baseline_lap_seconds, True)
        self.baseline_fuel_liters = _measurement("baseline_fuel_liters", baseline_fuel_liters)
        self._laps = {}
        self._order = []

    @property
    def lap_history(self):
        # type: () -> tuple
        """Immutable lap records in recording order."""
        return tuple(self._laps[number] for number in self._order)

    def reset_session(self):
        # type: () -> None
        """Clear laps; retain the explicitly configured baseline."""
        self._laps.clear()
        self._order[:] = []

    def record_lap(self, lap_number, lap_time_seconds, fuel_liters,
                   valid=True, complete=True, refueled=False):
        # type: (int, float, float, bool, bool, bool) -> object
        """Return a LapPerformance, or None for an explicitly excluded lap.

        Malformed measurements and duplicate lap IDs raise ValueError rather
        than overwriting history. fuel_liters means consumption for this lap.
        """
        if not valid or not complete or refueled:
            return None
        if isinstance(lap_number, bool) or not isinstance(lap_number, int) or lap_number < 1:
            raise ValueError("lap_number must be a positive integer")
        time_seconds = _measurement("lap_time_seconds", lap_time_seconds, True)
        fuel = _measurement("fuel_liters", fuel_liters)
        if lap_number in self._laps:
            raise ValueError("Lap already recorded: {0}".format(lap_number))
        lap = LapPerformance(lap_number, time_seconds, fuel)
        self._laps[lap_number] = lap
        self._order.append(lap_number)
        return lap

    def compare_lap(self, lap_number):
        # type: (int) -> PaceFuelComparison
        """Compare a recorded lap; unknown lap numbers raise KeyError."""
        lap = self._laps[lap_number]
        loss = lap.lap_time_seconds - self.baseline_lap_seconds
        saving = self.baseline_fuel_liters - lap.fuel_liters
        percentage = (saving / self.baseline_fuel_liters * 100.0
                      if self.baseline_fuel_liters > 0 else None)
        efficiency = saving / loss if loss > 0 else None
        for value in (percentage, efficiency):
            if value is not None and not math.isfinite(value):
                raise ValueError("Comparison exceeds finite numeric range")
        return PaceFuelComparison(lap, self.baseline_lap_seconds, self.baseline_fuel_liters,
                                 loss, saving, percentage, efficiency)

    def efficient_laps(self, max_pace_loss_seconds=0.5, min_fuel_saved_liters=0.0):
        # type: (float, float) -> tuple
        """Find strictly fuel-saving laps within the configured pace tolerance.

        Faster laps qualify too. Rank by most fuel saved, then least pace loss,
        then lap number; do not rank by a ratio undefined at equal/faster pace.
        """
        max_loss = _measurement("max_pace_loss_seconds", max_pace_loss_seconds)
        min_saving = _measurement("min_fuel_saved_liters", min_fuel_saved_liters)
        candidates = []
        for number in self._order:
            result = self.compare_lap(number)
            if (result.fuel_saved_liters > 0 and result.fuel_saved_liters >= min_saving
                    and result.pace_loss_seconds <= max_loss):
                candidates.append(result)
        return tuple(sorted(candidates, key=lambda item: (
            -item.fuel_saved_liters, item.pace_loss_seconds, item.lap.lap_number)))

    def best_efficient_lap(self, max_pace_loss_seconds=0.5, min_fuel_saved_liters=0.0):
        # type: (float, float) -> object
        """Return the highest ranked comparison, or None when none qualify."""
        candidates = self.efficient_laps(max_pace_loss_seconds, min_fuel_saved_liters)
        return candidates[0] if candidates else None
