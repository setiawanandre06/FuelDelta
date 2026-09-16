"""Pace versus fuel arithmetic, candidate selection, and rejected laps."""

import pytest

from fueldelta.analysis import PaceFuelAnalyzer


def test_requested_tradeoff():
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    analyzer.record_lap(23, 78.8, 2.37)
    result = analyzer.compare_lap(23)
    assert result.pace_loss_seconds == pytest.approx(0.30)
    assert result.fuel_saved_liters == pytest.approx(0.13)
    assert result.fuel_saved_percentage == pytest.approx(5.2)
    assert result.fuel_saved_per_second_lost == pytest.approx(0.4333333333)
    assert result.baseline_lap_seconds == 78.5
    assert result.baseline_fuel_liters == 2.5


def test_find_saving_laps_close_to_race_pace():
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    for number, seconds, fuel in [(21, 78.422, 2.53), (22, 78.511, 2.49),
                                  (23, 78.762, 2.38), (24, 78.910, 2.32)]:
        analyzer.record_lap(number, seconds, fuel)
    assert [lap.lap_number for lap in analyzer.lap_history] == [21, 22, 23, 24]
    assert analyzer.best_efficient_lap(0.30).lap.lap_number == 23
    assert analyzer.best_efficient_lap(0.50).lap.lap_number == 24
    assert analyzer.best_efficient_lap(0.30, 0.15) is None
    assert analyzer.compare_lap(21).fuel_saved_liters < 0


@pytest.mark.parametrize("seconds", [78.0, 78.5])
def test_faster_or_equal_pace_has_no_division_by_nonpositive_loss(seconds):
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    analyzer.record_lap(1, seconds, 2.3)
    result = analyzer.best_efficient_lap(0)
    assert result.lap.lap_number == 1
    assert result.fuel_saved_per_second_lost is None
    assert result.pace_loss_seconds <= 0


def test_zero_baseline_fuel_percentage_is_undefined():
    analyzer = PaceFuelAnalyzer(78.5, 0)
    analyzer.record_lap(1, 79, 0)
    assert analyzer.compare_lap(1).fuel_saved_percentage is None
    assert analyzer.compare_lap(1).fuel_saved_per_second_lost == 0
    assert analyzer.best_efficient_lap() is None


def test_signed_loss_and_saving_are_preserved():
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    analyzer.record_lap(1, 79, 3)
    result = analyzer.compare_lap(1)
    assert result.fuel_saved_liters == -0.5
    assert result.fuel_saved_percentage == -20
    assert result.fuel_saved_per_second_lost == -1
    assert analyzer.best_efficient_lap() is None


def test_exact_filter_boundaries_and_deterministic_ties():
    analyzer = PaceFuelAnalyzer(80, 3)
    analyzer.record_lap(3, 80.5, 2.5)
    analyzer.record_lap(2, 80, 2.5)
    analyzer.record_lap(1, 80, 2.5)
    assert [x.lap.lap_number for x in analyzer.efficient_laps(0.5, 0.5)] == [1, 2, 3]


@pytest.mark.parametrize("flags", [{"valid": False}, {"complete": False}, {"refueled": True}])
def test_excluded_laps_do_not_enter_history(flags):
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    assert analyzer.record_lap(1, 79, 2.0, **flags) is None
    assert analyzer.lap_history == ()
    assert analyzer.best_efficient_lap() is None


def test_duplicate_lap_rejected_and_session_reset():
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    analyzer.record_lap(1, 79, 2.4)
    history = analyzer.lap_history
    with pytest.raises(ValueError):
        analyzer.record_lap(1, 79, 2.1)
    analyzer.reset_session()
    assert analyzer.lap_history == ()
    assert history[0].fuel_liters == 2.4
    analyzer.record_lap(1, 79, 2.3)
    assert analyzer.compare_lap(1).baseline_lap_seconds == 78.5
    with pytest.raises(AttributeError):
        history[0].fuel_liters = 1


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), "78.5"])
def test_invalid_measurements_and_baselines(value):
    with pytest.raises(ValueError):
        PaceFuelAnalyzer(value, 2.5)
    with pytest.raises(ValueError):
        PaceFuelAnalyzer(78.5, value)
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    with pytest.raises(ValueError):
        analyzer.record_lap(1, value, 2.4)
    with pytest.raises(ValueError):
        analyzer.record_lap(1, 79, value)
    with pytest.raises(ValueError):
        analyzer.efficient_laps(value)
    with pytest.raises(ValueError):
        analyzer.efficient_laps(min_fuel_saved_liters=value)


@pytest.mark.parametrize("number", [0, -1, True, 1.5, None])
def test_invalid_lap_number(number):
    with pytest.raises(ValueError):
        PaceFuelAnalyzer(78.5, 2.5).record_lap(number, 79, 2.4)


def test_zero_time_and_unknown_lap():
    with pytest.raises(ValueError):
        PaceFuelAnalyzer(0, 2.5)
    analyzer = PaceFuelAnalyzer(78.5, 2.5)
    with pytest.raises(ValueError):
        analyzer.record_lap(1, 0, 2.4)
    with pytest.raises(KeyError):
        analyzer.compare_lap(1)
