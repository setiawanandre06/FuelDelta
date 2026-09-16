"""Stint arithmetic, safety reserve policy, and analyzer interoperability."""

import pytest

from fueldelta.analysis import FuelConsumptionAnalyzer
from fueldelta.models import StintProjection
from fueldelta.strategy import project_stint


def test_requested_sixty_minute_projection():
    result = project_stint(120.0, 3600.0, 78.5, 2.5)
    assert isinstance(result, StintProjection)
    assert result.estimated_laps == pytest.approx(45.85987261146497)
    assert result.estimated_fuel_required == pytest.approx(114.64968152866243)
    assert result.estimated_finish_fuel == pytest.approx(5.35031847133757)
    assert result.safety_fuel_required == 2.5
    assert result.total_fuel_required == pytest.approx(117.14968152866243)
    assert result.fuel_margin == pytest.approx(2.85031847133757)
    assert result.estimated_stint_duration == 3600.0
    assert result.status == "SAFE"


@pytest.mark.parametrize("fuel,finish,margin,status", [
    (23.0, 3.0, 1.0, "SAFE"), (22.0, 2.0, 0.0, "SAFE"),
    (21.0, 1.0, -1.0, "UNSAFE"), (19.0, -1.0, -3.0, "UNSAFE"),
    (0.0, -20.0, -22.0, "UNSAFE"),
])
def test_status_includes_reserve_and_preserves_deficits(fuel, finish, margin, status):
    result = project_stint(fuel, 600.0, 60.0, 2.0)
    assert result.estimated_finish_fuel == finish
    assert result.fuel_margin == margin
    assert result.status == status
    assert result.estimated_stint_duration == 600.0


@pytest.mark.parametrize("laps,liters,reserve", [
    (0.0, 0.0, 0.0), (0.5, 0.0, 1.0), (2.0, 0.0, 4.0),
    (0.0, 3.0, 3.0), (1.5, 3.0, 6.0),
])
def test_configurable_additive_safety_reserve(laps, liters, reserve):
    result = project_stint(30.0, 600.0, 60.0, 2.0, laps, liters)
    assert result.estimated_laps == 10.0
    assert result.estimated_fuel_required == 20.0
    assert result.estimated_finish_fuel == 10.0
    assert result.safety_fuel_required == reserve
    assert result.total_fuel_required == 20.0 + reserve
    assert result.fuel_margin == 10.0 - reserve


def test_fractional_laps_are_not_rounded_before_calculating_fuel():
    result = project_stint(10.0, 30.0, 60.0, 2.0, safety_laps=0.0)
    assert result.estimated_laps == 0.5
    assert result.estimated_fuel_required == 1.0


def test_status_uses_unrounded_values():
    result = project_stint(21.9999, 600.0, 60.0, 2.0)
    assert result.status == "UNSAFE"
    assert result.fuel_margin < 0


def test_zero_consumption_is_supported_without_division_by_zero():
    result = project_stint(0.0, 600.0, 60.0, 0.0)
    assert result.estimated_fuel_required == 0.0
    assert result.fuel_margin == 0.0
    assert result.status == "SAFE"
    assert project_stint(0, 600, 60, 0, safety_fuel_liters=1).status == "UNSAFE"


@pytest.mark.parametrize("field", [
    "fuel_liters", "target_duration_seconds", "average_lap_seconds",
    "consumption_liters_per_lap", "safety_laps", "safety_fuel_liters",
])
@pytest.mark.parametrize("value", [-1.0, None, True, "2.5", float("nan"), float("inf")])
def test_invalid_inputs_are_rejected(field, value):
    arguments = dict(fuel_liters=120.0, target_duration_seconds=3600.0,
                     average_lap_seconds=78.5, consumption_liters_per_lap=2.5)
    arguments[field] = value
    with pytest.raises(ValueError):
        project_stint(**arguments)


@pytest.mark.parametrize("duration,lap_time", [(0.0, 60.0), (600.0, 0.0)])
def test_duration_and_lap_time_must_be_positive(duration, lap_time):
    with pytest.raises(ValueError):
        project_stint(120.0, duration, lap_time, 2.5)


def test_projection_overflow_is_rejected():
    with pytest.raises(ValueError):
        project_stint(120.0, 1e308, 1e-308, 2.5)
    with pytest.raises(ValueError):
        project_stint(10 ** 1000, 600, 60, 2.5)


def test_consumption_analyzer_can_supply_average_without_source_dependency():
    analyzer = FuelConsumptionAnalyzer()
    for used in (2.52, 2.47, 2.44, 2.50, 2.45):
        analyzer.record_lap(10.0, 10.0 - used)
    result = project_stint(120.0, 3600.0, 78.5, analyzer.average_consumption)
    assert result.estimated_fuel_required == pytest.approx(113.54904458598726)
    assert result.status == "SAFE"


def test_missing_analyzer_average_is_not_assumed_zero():
    with pytest.raises(ValueError):
        project_stint(120.0, 3600.0, 78.5, FuelConsumptionAnalyzer().average_consumption)
