"""Paced capture orchestration, separate from CLI presentation."""

import math
import time

from .recording import SessionRecorder


def capture_session(source, root_directory, target_duration_minutes,
                    sample_rate_hz=10.0, duration_seconds=0.0,
                    clock=time.monotonic, sleep=time.sleep, on_started=None):
    """Record until EOF, Ctrl+C, unavailable data, session change, or time limit.

    Source ownership stays with the caller. No catch-up bursts are generated
    after a slow read. Duration 0 means unlimited. AC unavailable errors propagate
    after finalizing the partial recording; a new invocation starts a new file.
    """
    for name, value in (("sample_rate_hz", sample_rate_hz), ("duration_seconds", duration_seconds)):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError(name + " must be finite and nonnegative")
    if sample_rate_hz == 0:
        raise ValueError("sample_rate_hz must be positive")
    interval = 1.0 / sample_rate_hz
    first = source.read()
    generation = getattr(source, "session_generation", None)
    identity = (source.car, source.track)
    recorder = SessionRecorder(root_directory, source.car, source.track,
                               target_duration_minutes, sample_rate_hz)
    reason = "error"
    try:
        recorder.record(first)
        if on_started is not None:
            on_started(recorder.directory)
        started = clock()
        previous_poll = started
        while True:
            delay = max(0.0, previous_poll + interval - clock())
            if duration_seconds and clock() + delay >= started + duration_seconds:
                reason = "duration_limit"
                break
            sleep(delay)
            if duration_seconds and clock() >= started + duration_seconds:
                reason = "duration_limit"
                break
            previous_poll = clock()
            try:
                sample = source.read()
            except StopIteration:
                reason = "source_exhausted"
                break
            if (getattr(source, "session_generation", None) != generation
                    or (source.car, source.track) != identity
                    or sample.timestamp < recorder.metadata["last_timestamp"]):
                reason = "session_changed"
                break
            recorder.record(sample)
    except KeyboardInterrupt:
        reason = "interrupted"
    finally:
        recorder.close(reason)
    return recorder.directory
