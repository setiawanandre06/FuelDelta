"""Read live Assetto Corsa telemetry from an external Windows Python process."""

import argparse
import math
import sys
import time

from fueldelta.telemetry import AssettoCorsaTelemetrySource, TelemetryUnavailable


def main(argv=None):
    parser = argparse.ArgumentParser(description="FuelDelta live AC telemetry debug reader")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between reads")
    parser.add_argument("--samples", type=int, default=0, help="Stop after N samples; 0 runs until Ctrl+C")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval <= 0 or args.samples < 0:
        parser.error("interval must be positive and finite; samples must be nonnegative")
    try:
        with AssettoCorsaTelemetrySource() as source:
            count = 0
            while args.samples == 0 or count < args.samples:
                sample = source.read()
                if count == 0:
                    print("Connected to Assetto Corsa")
                print("\nCar: {0}\nTrack: {1}".format(source.car, source.track))
                print("Fuel:       {0:.2f} L".format(sample.fuel_liters))
                print("Speed:      {0:.0f} km/h".format(sample.speed_kmh))
                print("Throttle:   {0:.0%}".format(sample.throttle))
                print("Brake:      {0:.0%}".format(sample.brake))
                print("RPM:        {0}\nLap:        {1}".format(sample.rpm, sample.lap_number))
                sys.stdout.flush()
                count += 1
                if args.samples == 0 or count < args.samples:
                    time.sleep(args.interval)
    except TelemetryUnavailable as error:
        print("Telemetry unavailable: {0}".format(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
