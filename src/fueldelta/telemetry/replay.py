"""Deterministic, unpaced CSV replay of recorded TelemetrySample values."""

import csv
import json
import os

from fueldelta.models import TelemetrySample
from .source import TelemetrySource
from .recording import FIELDS, INTEGER_FIELDS, sample_values


class ReplayTelemetrySource(TelemetrySource):
    """Read a session directory or telemetry.csv; reset() replays it again.

    Original timestamps are preserved. read() never sleeps. Bad rows raise
    ValueError with their line number and are not silently skipped.
    """

    def __init__(self, path):
        # type: (str) -> None
        csv_path = os.path.join(path, "telemetry.csv") if os.path.isdir(path) else path
        metadata_path = os.path.join(os.path.dirname(csv_path), "session.json")
        self.metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, encoding="utf-8") as stream:
                self.metadata = json.load(stream)
            if not isinstance(self.metadata, dict) or self.metadata.get("schema_version") != 1:
                raise ValueError("Unsupported session metadata schema")
        self._file = open(csv_path, newline="", encoding="utf-8")
        try:
            self.reset()
        except Exception:
            self.close()
            raise

    def reset(self):
        # type: () -> None
        if self._file.closed:
            raise ValueError("Replay source is closed")
        self._file.seek(0)
        self._reader = csv.reader(self._file, strict=True)
        if tuple(next(self._reader, ())) != FIELDS:
            raise ValueError("Unsupported telemetry CSV header")
        self._last_timestamp = None
        self._failed = False

    def read(self):
        # type: () -> TelemetrySample
        if self._file.closed:
            raise ValueError("Replay source is closed")
        if self._failed:
            raise ValueError("Replay failed; reset or repair the recording")
        try:
            row = next(self._reader)
            if len(row) != len(FIELDS):
                raise ValueError("Wrong column count")
            values = [int(value) if field in INTEGER_FIELDS else float(value)
                      for field, value in zip(FIELDS, row)]
            sample = TelemetrySample(*values)
            sample_values(sample)
            if self._last_timestamp is not None and sample.timestamp < self._last_timestamp:
                raise ValueError("Timestamp moved backwards")
            self._last_timestamp = sample.timestamp
            return sample
        except (ValueError, csv.Error) as error:
            self._failed = True
            raise ValueError("Invalid telemetry at CSV line {0}: {1}".format(
                self._reader.line_num, error))

    def close(self):
        # type: () -> None
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
