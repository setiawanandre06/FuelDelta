"""Versioned CSV persistence for internal telemetry; no AC-specific fields."""

import csv
import datetime
import json
import math
import os
import re
import uuid

from fueldelta.models import TelemetrySample


FIELDS = ("timestamp", "fuel_liters", "speed_kmh", "throttle", "brake", "rpm",
          "gear", "lap_number", "lap_time_ms", "normalized_position")
INTEGER_FIELDS = ("rpm", "gear", "lap_number", "lap_time_ms")


def sample_values(sample):
    # type: (TelemetrySample) -> list
    """Validate without rounding, clamping, or changing the model."""
    if not isinstance(sample, TelemetrySample):
        raise ValueError("Expected a TelemetrySample")
    values = []
    for field in FIELDS:
        value = getattr(sample, field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Invalid numeric field: " + field)
        if field in INTEGER_FIELDS and not isinstance(value, int):
            raise ValueError("Expected integer field: " + field)
        if not math.isfinite(value) or value < (-1 if field == "gear" else 0):
            raise ValueError("Out-of-range field: " + field)
        values.append(value)
    if (sample.throttle > 1 or sample.brake > 1 or sample.normalized_position >= 1
            or sample.lap_number < 1):
        raise ValueError("Invalid pedal, lap number, or normalized position")
    return values


def _slug(value):
    # type: (str) -> str
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:80] or "unknown"


class SessionRecorder(object):
    """Write one observation epoch to a unique session directory.

    Use a context manager or close(). Rows are flushed after every sample.
    Metadata is atomically replaced after each update; abrupt termination may
    leave metadata counts behind the CSV, marked recording rather than closed.
    """

    def __init__(self, root_directory, car, track, target_duration_minutes,
                 sample_rate_hz=10.0):
        # type: (str, str, str, float, float) -> None
        for name, value in (("target duration", target_duration_minutes),
                            ("sample rate", sample_rate_hz)):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(name + " must be positive and finite")
        if not isinstance(car, str) or not car or not isinstance(track, str) or not track:
            raise ValueError("car and track must be nonempty strings")
        now = datetime.datetime.now(datetime.timezone.utc)
        name = "{0}_{1}_{2}_{3}".format(now.strftime("%Y-%m-%d"), _slug(track),
                                      _slug(car), uuid.uuid4().hex[:12])
        self.directory = os.path.join(root_directory, name)
        os.makedirs(self.directory)
        self._file = None
        self._last_timestamp = None
        self.metadata = dict(schema_version=1, car=car, track=track, initial_fuel=None,
                             target_duration_minutes=target_duration_minutes,
                             sample_rate_hz=sample_rate_hz, created_at_utc=now.isoformat(),
                             sample_count=0, first_timestamp=None, last_timestamp=None,
                             status="recording", stop_reason=None)
        try:
            self._save_metadata()
            self._file = open(os.path.join(self.directory, "telemetry.csv"), "w",
                              newline="", encoding="utf-8")
            self._writer = csv.writer(self._file)
            self._writer.writerow(FIELDS)
            self._file.flush()
        except Exception:
            if self._file is not None:
                self._file.close()
            raise

    def _save_metadata(self):
        # type: () -> None
        temporary = os.path.join(self.directory, "session.json.tmp")
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(self.metadata, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, os.path.join(self.directory, "session.json"))

    def record(self, sample):
        # type: (TelemetrySample) -> None
        if self._file is None or self._file.closed:
            raise ValueError("Recorder is closed")
        values = sample_values(sample)
        if self._last_timestamp is not None and sample.timestamp < self._last_timestamp:
            raise ValueError("Timestamp moved backwards; start a new recording")
        self._writer.writerow(values)
        self._file.flush()
        if self.metadata["sample_count"] == 0:
            self.metadata["initial_fuel"] = sample.fuel_liters
            self.metadata["first_timestamp"] = sample.timestamp
        self._last_timestamp = sample.timestamp
        self.metadata["last_timestamp"] = sample.timestamp
        self.metadata["sample_count"] += 1
        if self.metadata["sample_count"] == 1:
            self._save_metadata()

    def close(self, reason="completed"):
        # type: (str) -> None
        if self._file is not None and not self._file.closed:
            self._file.close()
            self.metadata["status"] = "closed"
            self.metadata["stop_reason"] = reason
            self._save_metadata()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close("error" if exc_type is not None else "completed")
