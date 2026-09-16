"""Timed stint projections using average pace and fuel consumption."""

import math

from fueldelta.models import StintProjection


def _number(name, value, positive=False):
    # type: (str, object, bool) -> float
    """Normalize finite numeric inputs, rejecting booleans and missing data."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("{0} must be a number".format(name))
    try:
        result = float(value)
    except OverflowError:
        raise ValueError("{0} is too large".format(name))
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        requirement = "positive" if positive else "nonnegative"
        raise ValueError("{0} must be finite and {1}".format(name, requirement))
    return result


def project_stint(fuel_liters, target_duration_seconds, average_lap_seconds,
                  consumption_liters_per_lap, safety_laps=1.0,
                  safety_fuel_liters=0.0):
    # type: (float, float, float, float, float, float) -> StintProjection
    """Project a timed stint without rounding up fractional laps.

    Safety reserve is safety_laps * consumption + safety_fuel_liters.
    Both margins are additive; set safety_laps=0 for a liters-only reserve.
    SAFE means the full target plus reserve fits in the available fuel.
    Zero consumption is supported; missing consumption must not be treated
    as zero. Negative finish fuel and margin express deficits, not tank fuel.
    """
    fuel = _number("fuel_liters", fuel_liters)
    duration = _number("target_duration_seconds", target_duration_seconds, True)
    lap_seconds = _number("average_lap_seconds", average_lap_seconds, True)
    consumption = _number("consumption_liters_per_lap", consumption_liters_per_lap)
    reserve_laps = _number("safety_laps", safety_laps)
    reserve_liters = _number("safety_fuel_liters", safety_fuel_liters)

    laps = duration / lap_seconds
    required = laps * consumption
    reserve = reserve_laps * consumption + reserve_liters
    total = required + reserve
    if not all(math.isfinite(value) for value in (laps, required, reserve, total)):
        raise ValueError("Projection exceeds finite numeric range")
    finish = fuel - required
    margin = fuel - total
    return StintProjection(laps, required, finish, margin, duration, reserve,
                           total, "SAFE" if margin >= 0 else "UNSAFE")
