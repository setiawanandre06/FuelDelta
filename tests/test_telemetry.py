"""Verify the internal model and source contract without game telemetry."""

import pytest

from fueldelta.models import TelemetrySample
from fueldelta.telemetry import FakeTelemetrySource, TelemetrySource


def test_sample_preserves_all_domain_fields():
    # type: () -> None
    values = dict(timestamp=12.5, fuel_liters=28.4, speed_kmh=123.0,
                  throttle=0.6, brake=0.1, rpm=5200, gear=4,
                  lap_number=2, lap_time_ms=2500, normalized_position=0.25)
    sample = TelemetrySample(**values)
    for field, value in values.items():
        assert getattr(sample, field) == value


def test_source_requires_read_implementation():
    # type: () -> None
    with pytest.raises(TypeError):
        TelemetrySource()


def test_fake_reads_custom_iterator_in_order_and_stays_exhausted():
    # type: () -> None
    first = TelemetrySample(1.0, 10.0, 80.0, 0.5, 0.0, 3000, 2, 1, 1000, 0.1)
    second = TelemetrySample(2.0, 9.9, 81.0, 0.4, 0.0, 3100, 2, 1, 2000, 0.2)
    source = FakeTelemetrySource(iter((first, second)))
    assert isinstance(source, TelemetrySource)
    assert source.read() is first
    assert source.read() is second
    for unused in range(2):
        with pytest.raises(StopIteration):
            source.read()


def test_explicit_empty_fake_has_no_demo_data():
    # type: () -> None
    with pytest.raises(StopIteration):
        FakeTelemetrySource([]).read()


def test_fake_rejects_non_sample_values():
    # type: () -> None
    with pytest.raises(TypeError):
        FakeTelemetrySource([{"fuel_liters": 30.0}]).read()


def test_demo_is_deterministic_and_instances_are_independent():
    # type: () -> None
    source = FakeTelemetrySource()
    other = FakeTelemetrySource()
    samples = [source.read() for unused in range(3)]
    assert [sample.timestamp for sample in samples] == [0.0, 1.0, 2.0]
    assert [sample.fuel_liters for sample in samples] == [30.0, 29.99, 29.985]
    first_other = other.read()
    assert vars(first_other) == vars(samples[0])
    assert first_other is not samples[0]
    with pytest.raises(StopIteration):
        source.read()
