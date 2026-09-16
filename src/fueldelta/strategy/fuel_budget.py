"""Fuel-saving targets for a stint in progress, independent of telemetry/UI."""

import math

from fueldelta.models import FuelBudget
from .stint import _number, project_stint


class FuelBudgetEngine(object):
    """Evaluate fresh observations against a fixed target duration.

    Times are seconds from the start of this stint, not wall-clock timestamps.
    This engine stores configuration only; each evaluation uses current fuel,
    pace, and consumption. Refueling requires no baseline adjustment. The caller
    supplies valid averages and resets elapsed time for a new stint.
    """

    def __init__(self, target_duration_seconds, safety_laps=1.0,
                 safety_fuel_liters=0.0):
        # type: (float, float, float) -> None
        self.target_duration_seconds = _number(
            "target_duration_seconds", target_duration_seconds, True)
        self.safety_laps = _number("safety_laps", safety_laps)
        self.safety_fuel_liters = _number("safety_fuel_liters", safety_fuel_liters)

    def evaluate(self, remaining_fuel_liters, elapsed_seconds,
                 average_lap_seconds, consumption_liters_per_lap):
        # type: (float, float, float, float) -> FuelBudget
        """Return a budget; missing/nonfinite/negative inputs raise ValueError.

        Zero consumption is allowed, but an unavailable analyzer average (None)
        is not zero. At/after the target no future driving or reserve is budgeted;
        TARGET_REACHED describes elapsed time, not historical success.
        """
        fuel = _number("remaining_fuel_liters", remaining_fuel_liters)
        elapsed = _number("elapsed_seconds", elapsed_seconds)
        lap_seconds = _number("average_lap_seconds", average_lap_seconds, True)
        consumption = _number("consumption_liters_per_lap", consumption_liters_per_lap)
        remaining = max(0.0, self.target_duration_seconds - elapsed)
        if remaining == 0:
            return FuelBudget(fuel, 0.0, 0.0, 0.0, fuel, fuel, 0.0,
                              None, consumption, 0.0, True, True, "TARGET_REACHED")

        projection = project_stint(fuel, remaining, lap_seconds, consumption,
                                   self.safety_laps, self.safety_fuel_liters)
        required_consumption, saving = self._saving_target(fuel, projection, consumption)
        if projection.estimated_finish_fuel < 0:
            status = "INSUFFICIENT_FUEL"
        elif projection.fuel_margin < 0:
            status = "BELOW_RESERVE"
        else:
            status = "ON_BUDGET"
        return FuelBudget(
            fuel, remaining, projection.estimated_laps,
            projection.total_fuel_required, projection.fuel_margin,
            projection.estimated_finish_fuel, projection.safety_fuel_required,
            required_consumption, consumption, saving,
            projection.estimated_finish_fuel >= 0,
            required_consumption is not None, status)

    def _saving_target(self, fuel, projection, consumption):
        # type: (float, object, float) -> tuple
        if fuel < self.safety_fuel_liters:
            # Even zero consumption cannot fund an already unaffordable reserve.
            return None, None
        budget_laps = projection.estimated_laps + self.safety_laps
        if not math.isfinite(budget_laps) or budget_laps <= 0:
            raise ValueError("Budget laps exceed numeric range")
        required = (fuel - self.safety_fuel_liters) / budget_laps
        if not math.isfinite(required):
            raise ValueError("Required consumption exceeds finite numeric range")
        return required, max(0.0, consumption - required)
