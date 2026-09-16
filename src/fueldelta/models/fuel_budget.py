"""Immutable snapshot of an ongoing stint's fuel budget."""

from collections import namedtuple


class FuelBudget(namedtuple("FuelBudgetValues", (
        "remaining_fuel remaining_time_seconds predicted_laps_remaining "
        "required_fuel delta projected_finish_fuel safety_fuel_required "
        "required_consumption current_consumption need_to_save "
        "can_finish_target can_meet_budget_by_saving status"))):
    """Fuel quantities are liters, consumption quantities are liters/lap.

    required_fuel includes reserve; projected_finish_fuel excludes reserve.
    required_consumption is the maximum affordable consumption, or None
    after the target or when the fixed reserve already exceeds available fuel.
    need_to_save is None when no consumption can satisfy the fixed reserve.
    Negative deltas/finish projections express deficits, not physical tank fuel.
    """

    __slots__ = ()
