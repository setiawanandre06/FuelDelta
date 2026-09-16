"""Calculation and telemetry discontinuity tests, with no game dependency."""

import pytest

from fueldelta.analysis import FuelConsumptionAnalyzer
from fueldelta.models import TelemetrySample
from fueldelta.telemetry import FakeTelemetrySource


def sample(timestamp, fuel, lap=1, lap_time_ms=0):
    # type: (float, float, int, int) -> TelemetrySample
    return TelemetrySample(timestamp, fuel, 100.0, 0.5, 0.0, 4000, 3,
                           lap, lap_time_ms, 0.0)


def test_manual_lap_and_empty_statistics():
    analyzer = FuelConsumptionAnalyzer()
    assert analyzer.last_lap_consumption is None
    assert analyzer.average_consumption is None
    assert analyzer.rolling_average() is None
    assert analyzer.record_lap(120.0, 117.52) == pytest.approx(2.48)
    assert analyzer.last_lap_consumption == pytest.approx(2.48)
    assert analyzer.rolling_average(10) == pytest.approx(2.48)


def test_history_and_rolling_average():
    analyzer = FuelConsumptionAnalyzer()
    for consumption in (2.52, 2.47, 2.44, 2.50, 2.45):
        analyzer.record_lap(10.0, 10.0 - consumption)
    assert analyzer.average_consumption == pytest.approx(2.476)
    assert analyzer.rolling_average() == pytest.approx(2.476)
    assert analyzer.rolling_average(2) == pytest.approx(2.475)
    snapshot = analyzer.consumption_history
    analyzer.record_lap(10.0, 7.0)
    assert len(snapshot) == 5
    assert len(analyzer.consumption_history) == 6
    assert analyzer.last_lap_consumption == 3.0
    assert analyzer.rolling_average() == pytest.approx(2.572)


@pytest.mark.parametrize("n", [0, -1, 1.5, True, None])
def test_invalid_rolling_window(n):
    with pytest.raises(ValueError):
        FuelConsumptionAnalyzer().rolling_average(n)


@pytest.mark.parametrize("gap", [0, -1, float("nan"), float("inf"), None, True])
def test_invalid_gap_configuration(gap):
    with pytest.raises(ValueError):
        FuelConsumptionAnalyzer(gap)


@pytest.mark.parametrize("start,end,valid,refueled", [
    (10.0, 11.0, True, False), (10.0, 9.0, False, False),
    (10.0, 9.0, True, True), (None, 9.0, True, False),
    (10.0, None, True, False), (float("nan"), 9.0, True, False),
    (10.0, float("inf"), True, False), (-1.0, 0.0, True, False),
    (10.0, -1.0, True, False), (True, 0.0, True, False),
])
def test_rejected_laps_do_not_change_statistics(start, end, valid, refueled):
    analyzer = FuelConsumptionAnalyzer()
    analyzer.record_lap(10.0, 8.0)
    assert analyzer.record_lap(start, end, valid, refueled) is None
    assert analyzer.consumption_history == (2.0,)


def test_zero_consumption_is_valid():
    analyzer = FuelConsumptionAnalyzer()
    assert analyzer.record_lap(10.0, 10.0) == 0.0
    assert analyzer.average_consumption == 0.0


def test_ten_fake_laps_end_to_end():
    consumptions = [2.52, 2.47, 2.44, 2.50, 2.45, 2.48, 2.46, 2.49, 2.43, 2.51]
    samples = []
    fuel = 120.0
    # Ten 60-second laps, sampled every second, plus the final boundary.
    for lap, consumption in enumerate(consumptions, 1):
        for second in range(60):
            samples.append(sample((lap - 1) * 60.0 + second,
                                  fuel - consumption * second / 60.0,
                                  lap, second * 1000))
        fuel -= consumption
    samples.append(sample(600.0, fuel, 11))
    source = FakeTelemetrySource(samples)
    analyzer = FuelConsumptionAnalyzer()
    while True:
        try:
            observation = source.read()
        except StopIteration:
            break
        analyzer.update(observation)
    assert analyzer.consumption_history == pytest.approx(consumptions)
    assert analyzer.last_lap_consumption == pytest.approx(2.51)
    assert analyzer.average_consumption == pytest.approx(2.475)
    assert analyzer.rolling_average() == pytest.approx(2.474)


def test_first_sample_is_only_a_baseline_and_partial_first_lap_is_skipped():
    analyzer = FuelConsumptionAnalyzer()
    assert analyzer.update(sample(1.0, 10.0, lap_time_ms=500)) is None
    assert analyzer.update(sample(2.0, 9.0, 2)) is None
    assert analyzer.update(sample(3.0, 7.0, 3)) == 2.0
    assert analyzer.consumption_history == (2.0,)


@pytest.mark.parametrize("pit_fuel", [9.5, 30.0])
def test_refueling_discards_whole_lap_even_if_net_fuel_decreases(pit_fuel):
    analyzer = FuelConsumptionAnalyzer()
    analyzer.record_lap(12.0, 10.0)
    analyzer.update(sample(0.0, 10.0))
    analyzer.update(sample(1.0, 9.0, lap_time_ms=1000))
    analyzer.update(sample(2.0, pit_fuel, lap_time_ms=2000))
    assert analyzer.update(sample(3.0, pit_fuel - 0.5, 2)) is None
    assert analyzer.update(sample(4.0, pit_fuel - 2.5, 3)) == 2.0
    assert analyzer.consumption_history == (2.0, 2.0)


def test_refueling_at_boundary_is_not_negative_consumption():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    assert analyzer.update(sample(1.0, 30.0, 2)) is None
    assert analyzer.update(sample(2.0, 28.0, 3)) == 2.0


def test_invalid_lap_stays_invalid_and_next_lap_recovers():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    analyzer.update(sample(1.0, 9.5, lap_time_ms=1000), lap_valid=False)
    analyzer.update(sample(2.0, 9.0, lap_time_ms=2000), lap_valid=True)
    assert analyzer.update(sample(3.0, 8.0, 2)) is None
    assert analyzer.update(sample(4.0, 6.0, 3)) == 2.0


def test_boundary_validity_applies_to_new_lap():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    assert analyzer.update(sample(1.0, 8.0, 2), lap_valid=False) == 2.0
    assert analyzer.update(sample(2.0, 6.0, 3)) is None
    analyzer.invalidate_current_lap()
    assert analyzer.update(sample(3.0, 4.0, 4)) is None


@pytest.mark.parametrize("missing", [None, sample(0.5, None),
                                       sample(0.5, float("nan")),
                                       sample(0.5, -1.0)])
def test_missing_fuel_or_telemetry_discards_lap(missing):
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    analyzer.update(missing)
    assert analyzer.update(sample(1.0, 8.0, 2)) is None
    assert analyzer.update(sample(2.0, 6.0, 3)) == 2.0


def test_gap_and_skipped_laps_never_count_as_single_lap():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    assert analyzer.update(sample(10.0, 8.0, 2, 1000)) is None
    assert analyzer.update(sample(11.0, 6.0, 3)) is None
    assert analyzer.update(sample(12.0, 4.0, 5)) is None
    assert analyzer.update(sample(13.0, 2.0, 6)) == 2.0
    assert analyzer.consumption_history == (2.0,)


@pytest.mark.parametrize("restart", [sample(0.0, 30.0, 2), sample(12.0, 30.0, 1)])
def test_session_rollback_clears_old_history(restart):
    analyzer = FuelConsumptionAnalyzer()
    analyzer.record_lap(10.0, 8.0)
    analyzer.update(sample(10.0, 10.0, 3))
    assert analyzer.update(restart) is None
    assert analyzer.consumption_history == ()
    assert analyzer.update(sample(restart.timestamp + 1, 27.0,
                                  restart.lap_number + 1)) == 3.0


def test_explicit_session_reset_clears_pending_lap_and_statistics():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.record_lap(10.0, 8.0)
    analyzer.update(sample(0.0, 10.0))
    analyzer.reset_session()
    assert analyzer.average_consumption is None
    assert analyzer.update(sample(1.0, 8.0, 2)) is None


def test_duplicate_timestamp_invalidates_pending_lap():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.update(sample(0.0, 10.0))
    analyzer.update(sample(0.0, 9.0))
    assert analyzer.update(sample(1.0, 8.0, 2)) is None


def test_input_mutation_does_not_change_previous_fuel():
    analyzer = FuelConsumptionAnalyzer()
    observation = sample(0.0, 10.0)
    analyzer.update(observation)
    observation.fuel_liters = 100.0
    assert analyzer.update(sample(1.0, 11.0, 2)) is None


def test_wrong_sample_type_raises():
    with pytest.raises(TypeError):
        FuelConsumptionAnalyzer().update({"fuel_liters": 10.0})
