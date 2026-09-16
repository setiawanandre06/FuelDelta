"""Budget accuracy, required saving, safety policy, and boundary cases."""

import pytest

from fueldelta.analysis import FuelConsumptionAnalyzer
from fueldelta.strategy import FuelBudgetEngine, project_stint
from fueldelta.ui.budget_cli import main


def test_twenty_minutes_into_stint_predicts_shortfall():
    result = FuelBudgetEngine(3600, safety_laps=0).evaluate(77, 1200, 72.5, 2.42)
    assert result.remaining_time_seconds == 2400
    assert result.predicted_laps_remaining == pytest.approx(33.10344827586207)
    assert result.required_fuel == pytest.approx(80.1103448275862)
    assert result.delta == pytest.approx(-3.1103448275862)
    assert result.projected_finish_fuel == pytest.approx(result.delta)
    assert result.required_consumption == pytest.approx(2.326041666666667)
    assert result.need_to_save == pytest.approx(0.093958333333333)
    assert result.status == "INSUFFICIENT_FUEL"
    assert not result.can_finish_target


def test_pace_changes_required_fuel_even_with_same_elapsed_time():
    engine = FuelBudgetEngine(3600, 0)
    fast = engine.evaluate(77, 1200, 60, 2.42)
    slow = engine.evaluate(77, 1200, 90, 2.42)
    assert fast.status == "INSUFFICIENT_FUEL"
    assert slow.status == "ON_BUDGET"
    assert slow.need_to_save == 0
    assert fast.required_fuel > slow.required_fuel


@pytest.mark.parametrize("fuel,status,can_finish", [
    (25, "ON_BUDGET", True), (22, "ON_BUDGET", True),
    (21, "BELOW_RESERVE", True), (20, "BELOW_RESERVE", True),
    (19, "INSUFFICIENT_FUEL", False), (0, "INSUFFICIENT_FUEL", False),
])
def test_status_distinguishes_target_from_reserve(fuel, status, can_finish):
    result = FuelBudgetEngine(600).evaluate(fuel, 0, 60, 2)
    assert result.required_fuel == 22
    assert result.projected_finish_fuel == fuel - 20
    assert result.delta == fuel - 22
    assert result.status == status
    assert result.can_finish_target is can_finish


@pytest.mark.parametrize("safety_laps,safety_liters", [(0, 0), (1, 0), (0, 3), (1.5, 3)])
def test_saving_target_funds_remaining_laps_and_configured_reserve(safety_laps, safety_liters):
    result = FuelBudgetEngine(600, safety_laps, safety_liters).evaluate(19, 0, 60, 2)
    affordable = result.required_consumption * (10 + safety_laps) + safety_liters
    assert affordable == pytest.approx(19)
    assert result.need_to_save == pytest.approx(2 - result.required_consumption)
    assert result.can_meet_budget_by_saving


def test_fixed_reserve_cannot_be_funded_by_any_saving():
    result = FuelBudgetEngine(600, 0, 3).evaluate(2, 0, 60, 0)
    assert result.status == "BELOW_RESERVE"
    assert result.required_consumption is None
    assert result.need_to_save is None
    assert not result.can_meet_budget_by_saving


def test_fuel_equal_to_fixed_reserve_requires_zero_consumption():
    result = FuelBudgetEngine(600, 0, 3).evaluate(3, 0, 60, 2)
    assert result.required_consumption == 0
    assert result.need_to_save == 2
    assert result.can_meet_budget_by_saving


@pytest.mark.parametrize("elapsed", [600, 700])
def test_target_elapsed_has_no_future_consumption_or_division_by_zero(elapsed):
    result = FuelBudgetEngine(600).evaluate(0, elapsed, 60, 2)
    assert result.status == "TARGET_REACHED"
    assert result.remaining_time_seconds == 0
    assert result.predicted_laps_remaining == 0
    assert result.required_fuel == 0
    assert result.required_consumption is None
    assert result.need_to_save == 0


def test_fractional_remaining_lap_and_zero_consumption():
    engine = FuelBudgetEngine(600, 0)
    result = engine.evaluate(1, 570, 60, 2)
    assert result.predicted_laps_remaining == 0.5
    assert result.required_fuel == 1
    assert result.status == "ON_BUDGET"
    assert engine.evaluate(0, 0, 60, 0).status == "ON_BUDGET"


def test_updates_refueling_and_restarted_elapsed_use_fresh_values():
    engine = FuelBudgetEngine(600, 0)
    before = engine.evaluate(1, 300, 60, 2)
    after = engine.evaluate(20, 300, 60, 2)
    restarted = engine.evaluate(20, 0, 60, 2)
    assert before.status == "INSUFFICIENT_FUEL"
    assert after.status == "ON_BUDGET"
    assert restarted.required_fuel == 20
    assert before.remaining_fuel == 1


def test_budget_matches_stint_projection_and_analyzer_average():
    analyzer = FuelConsumptionAnalyzer()
    analyzer.record_lap(10, 7.5)
    engine = FuelBudgetEngine(3600)
    budget = engine.evaluate(120, 0, 78.5, analyzer.average_consumption)
    projection = project_stint(120, 3600, 78.5, 2.5)
    assert budget.required_fuel == projection.total_fuel_required
    assert budget.delta == projection.fuel_margin
    assert budget.projected_finish_fuel == projection.estimated_finish_fuel


@pytest.mark.parametrize("field", ["remaining_fuel_liters", "elapsed_seconds",
                                   "average_lap_seconds", "consumption_liters_per_lap"])
@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), "2"])
def test_invalid_observations_are_rejected(field, value):
    arguments = dict(remaining_fuel_liters=77, elapsed_seconds=1200,
                     average_lap_seconds=72.5, consumption_liters_per_lap=2.42)
    arguments[field] = value
    with pytest.raises(ValueError):
        FuelBudgetEngine(3600).evaluate(**arguments)


@pytest.mark.parametrize("arguments", [(0,), (-1,), (None,), (3600, -1),
                                        (3600, 1, -1), (3600, float("inf"))])
def test_invalid_configuration(arguments):
    with pytest.raises(ValueError):
        FuelBudgetEngine(*arguments)


def test_zero_lap_time_and_overflow_are_rejected():
    with pytest.raises(ValueError):
        FuelBudgetEngine(600).evaluate(10, 0, 0, 2)
    with pytest.raises(ValueError):
        FuelBudgetEngine(1e308).evaluate(10, 0, 1e-308, 2)


def test_budget_cli_explains_shortfall(capsys):
    assert main(["--fuel", "77", "--minutes", "60", "--elapsed-minutes", "20",
                 "--lap-time", "1:12.500", "--consumption", "2.42",
                 "--safety-laps", "0"]) == 0
    output, errors = capsys.readouterr()
    assert "Required fuel:        80.11 L" in output
    assert "Delta:                -3.11 L" in output
    assert "Current consumption will not reach the target duration." in output
    assert errors == ""


def test_budget_cli_invalid_arguments(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--fuel", "77", "--minutes", "60", "--elapsed-minutes", "-1",
              "--lap-time", "72.5", "--consumption", "2.42"])
    assert error.value.code == 2
