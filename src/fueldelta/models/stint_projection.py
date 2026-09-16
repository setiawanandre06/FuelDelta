"""Source-independent result of a timed stint fuel calculation."""


class StintProjection(object):
    """Projection values: laps, liters, and duration in seconds.

    estimated_fuel_required excludes safety reserve; fuel_margin is the
    remaining fuel after both projected consumption and safety reserve.
    estimated_stint_duration is the requested duration, even if fuel is
    insufficient. It is not an estimate of time until the tank is empty.
    """

    def __init__(self, estimated_laps, estimated_fuel_required,
                 estimated_finish_fuel, fuel_margin, estimated_stint_duration,
                 safety_fuel_required, total_fuel_required, status):
        # type: (float, float, float, float, float, float, float, str) -> None
        self.estimated_laps = estimated_laps  # type: float
        self.estimated_fuel_required = estimated_fuel_required  # type: float
        self.estimated_finish_fuel = estimated_finish_fuel  # type: float
        self.fuel_margin = fuel_margin  # type: float
        self.estimated_stint_duration = estimated_stint_duration  # type: float
        self.safety_fuel_required = safety_fuel_required  # type: float
        self.total_fuel_required = total_fuel_required  # type: float
        self.status = status  # type: str
