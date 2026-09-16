"""Command-line argument parsing and presentation for stint projections."""

import argparse
import math

from fueldelta.strategy import project_stint


def parse_lap_time(value):
    # type: (str) -> float
    """Accept seconds or M:SS.sss, returning positive finite seconds."""
    try:
        if ":" in value:
            minutes, seconds_text = value.split(":")
            seconds = float(seconds_text)
            if not minutes.isdigit() or not 0 <= seconds < 60:
                raise ValueError
            seconds += int(minutes) * 60
        else:
            seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError
        return seconds
    except (ValueError, OverflowError):
        raise argparse.ArgumentTypeError("lap time must be positive seconds or M:SS.sss")


def main(argv=None):
    """Print a projection; malformed inputs use argparse's exit code 2."""
    parser = argparse.ArgumentParser(description="FuelDelta timed stint fuel calculator")
    parser.add_argument("--fuel", type=float, required=True, help="Available fuel in liters")
    parser.add_argument("--minutes", type=float, required=True, help="Target stint minutes")
    parser.add_argument("--lap-time", type=parse_lap_time, required=True,
                        help="Average lap time in seconds or M:SS.sss")
    parser.add_argument("--consumption", type=float, required=True, help="Liters per lap")
    parser.add_argument("--safety-laps", type=float, default=1.0,
                        help="Reserve in laps (default: 1.0)")
    parser.add_argument("--safety-fuel-liters", type=float, default=0.0,
                        help="Additional reserve in liters (default: 0.0)")
    args = parser.parse_args(argv)
    try:
        projection = project_stint(args.fuel, args.minutes * 60.0, args.lap_time,
                                   args.consumption, args.safety_laps,
                                   args.safety_fuel_liters)
    except ValueError as error:
        parser.error(str(error))

    print("Projected laps:       {0:.2f}".format(projection.estimated_laps))
    print("Projected fuel:       {0:.2f} L".format(projection.estimated_fuel_required))
    print("Finish fuel:          {0:.2f} L".format(projection.estimated_finish_fuel))
    print("Safety reserve:       {0:.2f} L".format(projection.safety_fuel_required))
    print("Fuel incl. reserve:   {0:.2f} L".format(projection.total_fuel_required))
    print("Fuel margin:          {0:.2f} L".format(projection.fuel_margin))
    print("Target duration:      {0:.2f} min".format(projection.estimated_stint_duration / 60.0))
    print("Status:               {0}".format(projection.status))
    return 0
