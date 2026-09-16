"""Map AC shared memory into the internal model; no fuel calculations."""

import ctypes
import math
import time

from fueldelta.models import TelemetrySample
from .source import TelemetrySource
from .ac_memory import Physics, Graphics, Static, WindowsMapping, TelemetryUnavailable, text_field


class AssettoCorsaTelemetrySource(TelemetrySource):
    """External Windows reader. Construct explicitly and close when finished.

    mapping_factory and clock are injection points for offline tests.
    timestamp is monotonic seconds since the first accepted observation of a
    reader epoch, not AC's absolute session elapsed time. See README caveats.
    """

    def __init__(self, mapping_factory=WindowsMapping, clock=time.monotonic,
                 stale_seconds=2.0):
        if not isinstance(stale_seconds, (int, float)) or not math.isfinite(stale_seconds) or stale_seconds <= 0:
            raise ValueError("stale_seconds must be positive and finite")
        self._clock = clock
        self._stale_seconds = stale_seconds
        self._pages = {}
        self._epoch = None
        self._previous = None
        self._packet = None
        self._packet_time = None
        self.car = ""
        self.track = ""
        self.session_generation = 0
        try:
            for name, layout in (("physics", Physics), ("graphics", Graphics), ("static", Static)):
                self._pages[name] = mapping_factory("acpmf_" + name, ctypes.sizeof(layout))
        except Exception:
            self.close()
            raise

    def _snapshot(self):
        # type: () -> tuple
        if not self._pages:
            raise TelemetryUnavailable("Telemetry source is closed")
        # Bounded double-copy check; AC offers no cross-page atomic transaction.
        for unused in range(5):
            first = tuple(self._pages[name].read() for name in ("graphics", "physics", "static"))
            second = tuple(self._pages[name].read() for name in ("graphics", "physics", "static"))
            if first == second:
                try:
                    return (Graphics.from_buffer_copy(first[0]),
                            Physics.from_buffer_copy(first[1]), Static.from_buffer_copy(first[2]))
                except ValueError:
                    raise TelemetryUnavailable("Shared-memory buffer is shorter than the supported AC layout")
        raise TelemetryUnavailable("AC updated during snapshot; retry")

    def read(self):
        # type: () -> TelemetrySample
        graphics, physics, static = self._snapshot()
        if graphics.status != 2:
            raise TelemetryUnavailable("AC is not live (off/replay/paused; status {0})".format(graphics.status))
        self._validate(graphics, physics)
        car, track = text_field(static.carModel), text_field(static.track)
        if not car or not track:
            raise TelemetryUnavailable("AC car/track metadata is not ready")
        now = self._clock()
        current = (car, track, graphics.session, graphics.completedLaps, graphics.iCurrentTime)
        previous = self._previous
        restarted = previous is not None and (
            current[:3] != previous[:3] or current[3] < previous[3]
            or (current[3] == previous[3] and current[4] < previous[4]))
        if self._epoch is None or restarted:
            self._epoch = now
            self._packet = None
            self.session_generation += 1
        if physics.packetId != self._packet:
            self._packet = physics.packetId
            self._packet_time = now
        elif now - self._packet_time >= self._stale_seconds:
            raise TelemetryUnavailable("AC physics stopped updating; reconnect if the game restarted")
        self._previous = current
        self.car, self.track = car, track
        return TelemetrySample(
            now - self._epoch, physics.fuel, physics.speedKmh, physics.gas,
            physics.brake, physics.rpms, physics.gear - 1,
            graphics.completedLaps + 1, graphics.iCurrentTime,
            graphics.normalizedCarPosition % 1.0)

    @staticmethod
    def _validate(graphics, physics):
        # type: (Graphics, Physics) -> None
        values = (physics.fuel, physics.speedKmh, physics.gas, physics.brake,
                  graphics.normalizedCarPosition)
        if (not all(math.isfinite(value) and value >= 0 for value in values)
                or physics.gas > 1 or physics.brake > 1
                or graphics.normalizedCarPosition > 1
                or physics.rpms < 0 or physics.gear < 0
                or graphics.completedLaps < 0 or graphics.iCurrentTime < 0):
            raise TelemetryUnavailable("AC returned invalid telemetry values")

    def close(self):
        # type: () -> None
        for page in self._pages.values():
            page.close()
        self._pages.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
