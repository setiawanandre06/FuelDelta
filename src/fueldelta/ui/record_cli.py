"""Record AC telemetry at a modest rate to a new session directory."""

import argparse
import sys

from fueldelta.telemetry import AssettoCorsaTelemetrySource, TelemetryUnavailable
from fueldelta.telemetry.capture import capture_session


def main(argv=None):
    parser = argparse.ArgumentParser(description="FuelDelta session recorder")
    parser.add_argument("--output", default="data", help="Parent directory for recordings")
    parser.add_argument("--target-minutes", type=float, default=60.0)
    parser.add_argument("--hz", type=float, choices=[10.0, 20.0], default=10.0)
    parser.add_argument("--seconds", type=float, default=0.0, help="Capture limit; 0 means Ctrl+C")
    args = parser.parse_args(argv)
    try:
        with AssettoCorsaTelemetrySource() as source:
            directory = capture_session(source, args.output, args.target_minutes,
                                        args.hz, args.seconds,
                                        on_started=lambda path: print("Recording: " + path))
        print("Saved: " + directory)
    except (TelemetryUnavailable, OSError, ValueError) as error:
        print("Recording stopped: {0}".format(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
