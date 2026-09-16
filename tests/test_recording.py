"""Recording/replay fidelity, capture pacing, and session boundaries."""

import csv
import json
import os

import pytest

from fueldelta.analysis import FuelConsumptionAnalyzer
from fueldelta.models import TelemetrySample
from fueldelta.telemetry import (FakeTelemetrySource, SessionRecorder,
                                ReplayTelemetrySource, TelemetryUnavailable)
from fueldelta.telemetry.capture import capture_session
from fueldelta.telemetry.recording import FIELDS


def observation(timestamp=0.0, fuel=120.0, lap=1):
    return TelemetrySample(timestamp, fuel, 100.1234567, 0.81234, 0.125,
                           4500, 3, lap, 0, 0.001)


def metadata(directory):
    with open(os.path.join(directory, "session.json"), encoding="utf-8") as stream:
        return json.load(stream)


def test_round_trip_all_fields_and_repeated_replay(tmpdir):
    samples = [observation(0), observation(0.1, 119.9991234567)]
    with SessionRecorder(str(tmpdir), "bmw_m4_gt3", "spa", 60) as recorder:
        for sample in samples:
            recorder.record(sample)
    details = metadata(recorder.directory)
    assert details["initial_fuel"] == 120
    assert details["car"] == "bmw_m4_gt3"
    assert details["track"] == "spa"
    assert details["target_duration_minutes"] == 60
    assert details["sample_rate_hz"] == 10
    assert details["sample_count"] == 2
    assert details["last_timestamp"] == 0.1
    assert details["status"] == "closed"
    with ReplayTelemetrySource(recorder.directory) as replay:
        for unused in range(3):
            replay.reset()
            for expected in samples:
                assert vars(replay.read()) == vars(expected)
            for attempt in range(2):
                with pytest.raises(StopIteration):
                    replay.read()


def test_ten_laps_have_identical_consumption_on_each_replay(tmpdir):
    expected = [2.52, 2.47, 2.44, 2.50, 2.45, 2.48, 2.46, 2.49, 2.43, 2.51]
    fuel = 120.0
    with SessionRecorder(str(tmpdir), "car", "track", 60) as recorder:
        recorder.record(observation(0, fuel))
        for index, used in enumerate(expected, 1):
            fuel -= used
            recorder.record(observation(index, fuel, index + 1))
    with ReplayTelemetrySource(recorder.directory) as replay:
        for unused in range(3):
            analyzer = FuelConsumptionAnalyzer()
            replay.reset()
            while True:
                try:
                    sample = replay.read()
                except StopIteration:
                    break
                analyzer.update(sample)
            assert analyzer.consumption_history == pytest.approx(expected)


def test_unique_safe_directories_and_empty_session(tmpdir):
    with SessionRecorder(str(tmpdir), "../car", "../../spa", 60) as first:
        pass
    with SessionRecorder(str(tmpdir), "../car", "../../spa", 60) as second:
        pass
    assert first.directory != second.directory
    assert os.path.dirname(first.directory) == str(tmpdir)
    assert metadata(first.directory)["initial_fuel"] is None
    with ReplayTelemetrySource(first.directory) as replay:
        with pytest.raises(StopIteration):
            replay.read()


def test_partial_recording_survives_exception_and_close_is_idempotent(tmpdir):
    with pytest.raises(RuntimeError):
        with SessionRecorder(str(tmpdir), "car", "track", 60) as recorder:
            recorder.record(observation())
            raise RuntimeError("interrupted work")
    recorder.close()
    assert metadata(recorder.directory)["stop_reason"] == "error"
    with ReplayTelemetrySource(recorder.directory) as replay:
        assert replay.read().fuel_liters == 120
    with pytest.raises(ValueError):
        recorder.record(observation())


def test_invalid_sample_or_time_rollback_does_not_append(tmpdir):
    with SessionRecorder(str(tmpdir), "car", "track", 60) as recorder:
        recorder.record(observation(1))
        with pytest.raises(ValueError):
            recorder.record(observation(0))
        with pytest.raises(ValueError):
            recorder.record(observation(2, float("nan")))
    assert metadata(recorder.directory)["sample_count"] == 1


@pytest.mark.parametrize("bad_row", [
    "0,120", "0,nan,1,0,0,900,1,1,0,0", "0,120,1,0,0,900.5,1,1,0,0",
    "0,120,1,0,0,900,1,0,0,0", "0,120,1,0,0,900,1,1,0,1",
])
def test_malformed_rows_fail_with_line_number_and_remain_failed(tmpdir, bad_row):
    path = str(tmpdir.join("telemetry.csv"))
    with open(path, "w", newline="", encoding="utf-8") as stream:
        stream.write(",".join(FIELDS) + "\n" + bad_row + "\n")
    with ReplayTelemetrySource(path) as replay:
        with pytest.raises(ValueError) as error:
            replay.read()
        assert "line 2" in str(error.value)
        with pytest.raises(ValueError):
            replay.read()


def test_bad_header_and_unsupported_metadata(tmpdir):
    path = str(tmpdir.join("telemetry.csv"))
    with open(path, "w") as stream:
        stream.write("fuel,timestamp\n")
    with pytest.raises(ValueError):
        ReplayTelemetrySource(path)
    with open(str(tmpdir.join("session.json")), "w") as stream:
        json.dump({"schema_version": 999}, stream)
    with pytest.raises(ValueError):
        ReplayTelemetrySource(path)


class Clock(object):
    def __init__(self):
        self.now = 0.0

    def read(self):
        return self.now

    def sleep(self, delay):
        self.now += delay


class LiveFake(object):
    car = "fake_car"
    track = "fake_track"
    session_generation = 1

    def __init__(self, clock):
        self.clock = clock
        self.read_times = []

    def read(self):
        self.read_times.append(self.clock.now)
        return observation(self.clock.now)


@pytest.mark.parametrize("hz", [10.0, 20.0])
def test_capture_polls_at_requested_rate(tmpdir, hz):
    clock = Clock()
    source = LiveFake(clock)
    directory = capture_session(source, str(tmpdir), 60, hz, 0.99,
                                clock.read, clock.sleep)
    assert len(source.read_times) == int(hz)
    assert source.read_times == pytest.approx([i / hz for i in range(int(hz))])
    assert metadata(directory)["stop_reason"] == "duration_limit"


def test_session_change_does_not_mix_epochs(tmpdir):
    clock = Clock()
    source = LiveFake(clock)
    def sleep(delay):
        clock.sleep(delay)
        source.session_generation += 1
    directory = capture_session(source, str(tmpdir), 60, clock=clock.read, sleep=sleep)
    assert metadata(directory)["sample_count"] == 1
    assert metadata(directory)["stop_reason"] == "session_changed"


def test_unavailable_data_finalizes_partial_capture(tmpdir):
    clock = Clock()
    source = LiveFake(clock)
    directories = []
    def sleep(delay):
        raise TelemetryUnavailable("paused")
    with pytest.raises(TelemetryUnavailable):
        capture_session(source, str(tmpdir), 60, clock=clock.read, sleep=sleep,
                        on_started=directories.append)
    assert metadata(directories[0])["sample_count"] == 1
    assert metadata(directories[0])["status"] == "closed"


def test_ctrl_c_finalizes_capture(tmpdir):
    clock = Clock()
    def sleep(delay):
        raise KeyboardInterrupt
    directory = capture_session(LiveFake(clock), str(tmpdir), 60,
                                clock=clock.read, sleep=sleep)
    assert metadata(directory)["stop_reason"] == "interrupted"


def test_capture_source_exhaustion(tmpdir):
    clock = Clock()
    source = FakeTelemetrySource([observation()])
    source.car, source.track = "car", "track"
    directory = capture_session(source, str(tmpdir), 60,
                                clock=clock.read, sleep=clock.sleep)
    assert metadata(directory)["stop_reason"] == "source_exhausted"
