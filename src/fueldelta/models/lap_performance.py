"""Immutable lap measurements and their comparison against race pace."""

from collections import namedtuple


class LapPerformance(namedtuple("LapPerformanceValues", "lap_number lap_time_seconds fuel_liters")):
    """One valid complete lap; fuel_liters is consumed fuel, not tank fuel."""

    __slots__ = ()


class PaceFuelComparison(namedtuple("PaceFuelComparisonValues", (
        "lap baseline_lap_seconds baseline_fuel_liters pace_loss_seconds "
        "fuel_saved_liters fuel_saved_percentage fuel_saved_per_second_lost"))):
    """Signed differences; ratios are None when their denominator is undefined.

    Negative pace loss means faster; negative fuel saving means more fuel used.
    L/second efficiency is only defined for positive pace loss.
    """

    __slots__ = ()
