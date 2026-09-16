"""Display a live-stint fuel budget from command-line inputs."""

import argparse

from fueldelta.strategy import FuelBudgetEngine
from .cli import parse_lap_time


def main(argv=None):
    """Calculate a budget, returning 0; invalid arguments exit with code 2."""
    parser = argparse.ArgumentParser(description="FuelDelta fuel budget engine")
    parser.add_argument("--fuel", type=float, required=True, help="Current fuel in liters")
    parser.add_argument("--minutes", type=float, required=True, help="Total target minutes")
    parser.add_argument("--elapsed-minutes", type=float, required=True)
    parser.add_argument("--lap-time", type=parse_lap_time, required=True)
    parser.add_argument("--consumption", type=float, required=True, help="Current liters/lap")
    parser.add_argument("--safety-laps", type=float, default=1.0)
    parser.add_argument("--safety-fuel-liters", type=float, default=0.0)
    args = parser.parse_args(argv)
    try:
        engine = FuelBudgetEngine(args.minutes * 60.0, args.safety_laps,
                                  args.safety_fuel_liters)
        budget = engine.evaluate(args.fuel, args.elapsed_minutes * 60.0,
                                 args.lap_time, args.consumption)
    except ValueError as error:
        parser.error(str(error))
    print("FUEL BUDGET")
    print("Remaining fuel:       {0:.2f} L".format(budget.remaining_fuel))
    print("Laps remaining:       {0:.2f}".format(budget.predicted_laps_remaining))
    print("Required fuel:        {0:.2f} L".format(budget.required_fuel))
    print("Delta:                {0:+.2f} L".format(budget.delta))
    print("Projected finish:     {0:+.2f} L".format(budget.projected_finish_fuel))
    print("Safety reserve:       {0:.2f} L".format(budget.safety_fuel_required))
    print("Current consumption:  {0:.3f} L/lap".format(budget.current_consumption))
    if budget.required_consumption is not None:
        print("Required consumption: {0:.3f} L/lap".format(budget.required_consumption))
        print("Need to save:         {0:.3f} L/lap".format(budget.need_to_save))
    print("Status:               {0}".format(budget.status))
    messages = {
        "INSUFFICIENT_FUEL": "Current consumption will not reach the target duration.",
        "BELOW_RESERVE": "Target is reachable, but the safety reserve is not covered.",
        "ON_BUDGET": "Current consumption covers the target and safety reserve.",
        "TARGET_REACHED": "Target duration has elapsed.",
    }
    print(messages[budget.status])
    if not budget.can_meet_budget_by_saving:
        print("Saving alone cannot cover the fixed fuel reserve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
