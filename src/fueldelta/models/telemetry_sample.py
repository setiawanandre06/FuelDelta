"""Source-independent telemetry values in FuelDelta's internal units."""


class TelemetrySample(object):
    """One observation, without any dependency on game memory structures.

    timestamp is elapsed seconds from the source's session start.
    throttle and brake are fractions in [0, 1]; normalized_position is lap
    progress in [0, 1). lap_number is one-based; lap_time_ms is elapsed time
    in the current lap. gear uses -1 for reverse, 0 for neutral, and 1+ for
    forward gears. These are internal conventions, not AC field mappings.

    Source adapters are responsible for normalization. This value container
    stores supplied values without conversion or clamping.
    """

    def __init__(self, timestamp, fuel_liters, speed_kmh, throttle, brake,
                 rpm, gear, lap_number, lap_time_ms, normalized_position):
        # type: (float, float, float, float, float, int, int, int, int, float) -> None
        self.timestamp = timestamp  # type: float
        self.fuel_liters = fuel_liters  # type: float
        self.speed_kmh = speed_kmh  # type: float
        self.throttle = throttle  # type: float
        self.brake = brake  # type: float
        self.rpm = rpm  # type: int
        self.gear = gear  # type: int
        self.lap_number = lap_number  # type: int
        self.lap_time_ms = lap_time_ms  # type: int
        self.normalized_position = normalized_position  # type: float
