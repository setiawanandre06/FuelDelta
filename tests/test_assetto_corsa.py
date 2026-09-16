"""AC ABI fixtures and adapter lifecycle tests without a running game."""

import ctypes
import mmap
import struct
import sys
import uuid

import pytest

from fueldelta.telemetry import AssettoCorsaTelemetrySource, TelemetryUnavailable
from fueldelta.telemetry.ac_memory import Physics, Graphics, Static, WindowsMapping
from fueldelta.ui import telemetry_cli


class Buffer(object):
    def __init__(self, data):
        self.data = data
        self.closed = False

    def read(self):
        return bytes(self.data)

    def close(self):
        self.closed = True


def fixture_pages():
    # Independently pack known Windows byte offsets, not ctypes-generated data.
    physics = bytearray(32)
    struct.pack_into("<ifffiiff", physics, 0,
                     100, 1.0, 0.0, 119.42, 4, 6712, 0.0, 237.0)
    graphics = bytearray(252)
    struct.pack_into("<iii", graphics, 0, 50, 2, 2)
    struct.pack_into("<i", graphics, 132, 2)
    struct.pack_into("<i", graphics, 140, 18500)
    struct.pack_into("<f", graphics, 248, 0.25)
    static = bytearray(200)
    car = "bmw_m4_gt3".encode("utf-16-le")
    track = "spa".encode("utf-16-le")
    static[68:68 + len(car)] = car
    static[134:134 + len(track)] = track
    return {"acpmf_physics": Buffer(physics), "acpmf_graphics": Buffer(graphics),
            "acpmf_static": Buffer(static)}


def source_fixture():
    pages = fixture_pages()
    now = [100.0]
    source = AssettoCorsaTelemetrySource(
        mapping_factory=lambda name, size: pages[name], clock=lambda: now[0])
    return source, pages, now


def test_windows_abi_prefix_sizes_and_offsets():
    assert ctypes.sizeof(Physics) == 32
    assert Physics.fuel.offset == 12
    assert ctypes.sizeof(Graphics) == 252
    assert Graphics.completedLaps.offset == 132
    assert Graphics.iCurrentTime.offset == 140
    assert Graphics.normalizedCarPosition.offset == 248
    assert ctypes.sizeof(Static) == 200
    assert Static.carModel.offset == 68
    assert Static.track.offset == 134


def test_mapping_to_internal_sample_and_metadata():
    source, pages, now = source_fixture()
    result = source.read()
    assert result.fuel_liters == pytest.approx(119.42)
    assert result.speed_kmh == 237
    assert result.throttle == 1
    assert result.brake == 0
    assert result.rpm == 6712
    assert result.gear == 3
    assert result.lap_number == 3
    assert result.lap_time_ms == 18500
    assert result.normalized_position == 0.25
    assert result.timestamp == 0
    assert source.car == "bmw_m4_gt3"
    assert source.track == "spa"
    now[0] += 0.5
    assert source.read().timestamp == 0.5
    struct.pack_into("<f", pages["acpmf_physics"].data, 12, 10)
    assert result.fuel_liters == pytest.approx(119.42)


@pytest.mark.parametrize("ac_gear,gear", [(0, -1), (1, 0), (2, 1), (7, 6)])
def test_gear_normalization(ac_gear, gear):
    source, pages, now = source_fixture()
    struct.pack_into("<i", pages["acpmf_physics"].data, 16, ac_gear)
    assert source.read().gear == gear


@pytest.mark.parametrize("status", [0, 1, 3])
def test_non_live_states_are_unavailable(status):
    source, pages, now = source_fixture()
    struct.pack_into("<i", pages["acpmf_graphics"].data, 4, status)
    with pytest.raises(TelemetryUnavailable):
        source.read()


def test_stale_packets_and_recovery():
    source, pages, now = source_fixture()
    source.read()
    now[0] += 2.1
    with pytest.raises(TelemetryUnavailable):
        source.read()
    struct.pack_into("<i", pages["acpmf_physics"].data, 0, 101)
    assert source.read().timestamp == pytest.approx(2.1)


def test_restart_resets_epoch_but_normal_lap_transition_does_not():
    source, pages, now = source_fixture()
    source.read()
    now[0] += 0.5
    struct.pack_into("<i", pages["acpmf_graphics"].data, 132, 3)
    struct.pack_into("<i", pages["acpmf_graphics"].data, 140, 0)
    assert source.read().timestamp == 0.5
    now[0] += 0.5
    struct.pack_into("<i", pages["acpmf_graphics"].data, 132, 0)
    assert source.read().timestamp == 0
    assert source.session_generation == 2


@pytest.mark.parametrize("fuel", [-1, float("nan"), float("inf")])
def test_invalid_fuel_is_not_forwarded(fuel):
    source, pages, now = source_fixture()
    struct.pack_into("<f", pages["acpmf_physics"].data, 12, fuel)
    with pytest.raises(TelemetryUnavailable):
        source.read()


def test_short_buffer_is_unavailable():
    source, pages, now = source_fixture()
    pages["acpmf_physics"].data = bytearray(1)
    with pytest.raises(TelemetryUnavailable):
        source.read()


def test_unstable_snapshot_is_bounded():
    source, pages, now = source_fixture()
    counter = [0]
    def changing():
        counter[0] += 1
        return struct.pack("<i", counter[0]) + bytes(28)
    pages["acpmf_physics"].read = changing
    with pytest.raises(TelemetryUnavailable):
        source.read()
    assert counter[0] == 10


def test_partial_connection_failure_closes_opened_pages():
    pages = fixture_pages()
    def opening(name, size):
        if name == "acpmf_static":
            raise TelemetryUnavailable("not present")
        return pages[name]
    with pytest.raises(TelemetryUnavailable):
        AssettoCorsaTelemetrySource(mapping_factory=opening)
    assert pages["acpmf_physics"].closed
    assert pages["acpmf_graphics"].closed


def test_context_manager_and_repeated_close():
    source, pages, now = source_fixture()
    with source:
        source.read()
    source.close()
    assert all(page.closed for page in pages.values())
    with pytest.raises(TelemetryUnavailable):
        source.read()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named mapping API")
def test_real_windows_mapping_reads_existing_test_buffer_and_never_creates_missing():
    name = "FuelDelta_test_" + uuid.uuid4().hex
    with pytest.raises(TelemetryUnavailable):
        WindowsMapping(name, 32)
    with mmap.mmap(-1, 32, tagname=name) as writer:
        writer[:4] = b"test"
        reader = WindowsMapping(name, 32)
        try:
            assert reader.read()[:4] == b"test"
            writer[:4] = b"next"
            assert reader.read()[:4] == b"next"
        finally:
            reader.close()
            reader.close()
    with pytest.raises(TelemetryUnavailable):
        WindowsMapping(name, 32)


def test_debug_cli_prints_only_after_valid_sample(monkeypatch, capsys):
    source, pages, now = source_fixture()
    monkeypatch.setattr(telemetry_cli, "AssettoCorsaTelemetrySource", lambda: source)
    assert telemetry_cli.main(["--samples", "1"]) == 0
    output, errors = capsys.readouterr()
    assert "Connected to Assetto Corsa" in output
    assert "119.42 L" in output
    assert "bmw_m4_gt3" in output
    assert all(page.closed for page in pages.values())


def test_debug_cli_connection_error_has_no_fake_success(monkeypatch, capsys):
    def unavailable():
        raise TelemetryUnavailable("AC not running")
    monkeypatch.setattr(telemetry_cli, "AssettoCorsaTelemetrySource", unavailable)
    assert telemetry_cli.main(["--samples", "1"]) == 1
    output, errors = capsys.readouterr()
    assert "Connected" not in output
    assert "AC not running" in errors
