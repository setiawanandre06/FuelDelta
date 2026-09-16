# FuelDelta

A Python 3.3.5 project that will read Assetto Corsa telemetry and coach
drivers to save fuel while minimizing lap-time loss. The internal telemetry
model, a fake source, a fuel consumption analyzer, and a command-line stint
calculator are available. Assetto Corsa integration and a graphical UI are not
implemented.

## Layout

- `src/fueldelta/telemetry`: telemetry access and normalization.
- `src/fueldelta/analysis`: fuel consumption analysis.
- `src/fueldelta/strategy`: race fuel planning and coaching calculations.
- `src/fueldelta/models`: shared data models.
- `src/fueldelta/ui`: presentation only.
- `tests`: pytest tests.

## Development

### Internal telemetry

Consumers depend on `fueldelta.models.TelemetrySample` and a source's `read()`
contract, never on Assetto Corsa memory structures. Python 3.3.5 uses a plain
class with type comments instead of a dataclass, and `TelemetrySource` is an
abstract base class instead of `typing.Protocol`. Duck-typed sources with the
same `read()` contract can also be used.

```python
from fueldelta.telemetry import FakeTelemetrySource

source = FakeTelemetrySource()
while True:
    try:
        sample = source.read()
    except StopIteration:
        break
    print(sample.timestamp, sample.fuel_liters)
```

The default source yields three deterministic samples without waiting. Pass an
iterable of `TelemetrySample` objects to supply your own scenario; an empty
iterable yields nothing. Exhaustion raises `StopIteration`; invalid items raise
`TypeError` when read. Custom samples are returned without copying.

Internal conventions: timestamp is seconds since session start, fuel is liters,
speed is km/h, throttle/brake are fractions from 0 to 1, RPM is engine revolutions
per minute, gear is -1 for reverse / 0 for neutral / 1+ for forward, lap numbers
start at 1, lap time is elapsed milliseconds in the current lap, and normalized
position is lap progress in [0, 1). Future adapters must normalize their input;
the model does not validate or clamp values. These conventions do not claim any
mapping to AC fields. The fake data is illustrative, not a physics simulation.

### Fuel consumption

`FuelConsumptionAnalyzer` in `fueldelta.analysis` accepts normalized telemetry
through `update(sample, lap_valid=True)`. It records completed valid laps and
returns their consumption in liters; otherwise it returns `None`. It depends
only on the internal model, not on the source or UI.

For already measured complete laps:

```python
from fueldelta.analysis import FuelConsumptionAnalyzer

analyzer = FuelConsumptionAnalyzer()
analyzer.record_lap(120.0, 117.52)  # approximately 2.48 liters
print(analyzer.last_lap_consumption)
print(analyzer.average_consumption)
print(analyzer.rolling_average(n=5))
```

To feed a source, call `analyzer.update(source.read())` for each observation
until the source raises `StopIteration`. `tests/test_fuel_consumption.py` includes
a complete 10-lap `FakeTelemetrySource` scenario sampled once per second,
including the start of lap 11 to close lap 10.

- `consumption_history` is an immutable snapshot of all accepted consumption
  values in the current session, in completion order. Rejected laps are omitted.
- `last_lap_consumption` means the latest accepted lap; rejected laps do not
  overwrite it. `average_consumption` uses the full session history.
- `rolling_average(n=5)` uses the latest n accepted laps, or fewer if necessary.
  Empty statistics return `None`; zero consumption is a valid measurement.
  A nonpositive or noninteger window raises `ValueError`.
- The first observation establishes a baseline. A first sample with
  `lap_time_ms != 0` is treated as a partial lap and excluded. Thereafter a
  consecutive lap-number increment closes the previous lap, using the new
  sample's fuel as its end fuel and the next lap's start fuel. These are sampled
  estimates; no exact crossing interpolation or AC field mapping is assumed.
- Any observed fuel increase invalidates the pending lap, including refueling
  whose net lap consumption would otherwise be positive. History is retained
  after pit refueling, and measurement resumes from the next lap boundary.
- `lap_valid=False` applies to the sample's own lap and stays invalid for that
  lap. To reject the previous lap before passing its closing boundary, call
  `invalidate_current_lap()`. Validity is supplied externally, not inferred from
  invented telemetry fields.
- Pass `None` for missing telemetry. Missing/negative/nonfinite fuel, invalid
  timestamp/lap metadata, repeated timestamps, gaps exceeding
  `max_sample_gap_seconds` (default 2.0), and skipped lap numbers discard affected
  measurements. After a missing boundary, a baseline is established at an exact
  lap-start sample or a subsequent observed boundary; incomplete laps are skipped.
- A timestamp or lap-number rollback automatically clears history as a session
  restart. Input must be ordered; old packets cannot be distinguished from a
  restart without a session ID. Call `reset_session()` for explicit restarts,
  including those whose counters do not roll back.
- Manual `record_lap(start_fuel_liters, end_fuel_liters, valid=True,
  refueled=False)` rejects invalid endpoints, fuel increases, invalid laps, and
  declared refueling. Callers must report refueling hidden between endpoints.
  Likewise, additions entirely between telemetry samples cannot be detected.
  Use manual recording or automatic updates for a given lap, not both, to avoid
  double counting. No partial final lap is recorded when a source ends.

All calculations use unrounded liters; round only for display. No dependencies
or Assetto Corsa integration are required.

### Race/stint fuel projection

From the project root in PowerShell, using the development environment:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m fueldelta --fuel 120 --minutes 60 --lap-time 78.5 --consumption 2.5 --safety-laps 1
```

Alternatively, after an editable install, use `python -m fueldelta` without
setting `PYTHONPATH`. `--lap-time 1:18.500` also accepts minutes and seconds.

```text
Projected laps:       45.86
Projected fuel:       114.65 L
Finish fuel:          5.35 L
Safety reserve:       2.50 L
Fuel incl. reserve:   117.15 L
Fuel margin:          2.85 L
Target duration:      60.00 min
Status:               SAFE
```

Calculation lives in `fueldelta.strategy`, independently of CLI presentation:

```python
from fueldelta.strategy import project_stint

projection = project_stint(
    fuel_liters=120.0,
    target_duration_seconds=3600.0,
    average_lap_seconds=78.5,
    consumption_liters_per_lap=2.5,
    safety_laps=1.0,
    safety_fuel_liters=0.0,
)
print(projection.status)
```

The result is `fueldelta.models.StintProjection` with these conventions:

| Field | Meaning |
| --- | --- |
| `estimated_laps` | Target seconds / average lap seconds, including fractional laps |
| `estimated_fuel_required` | Projected laps * consumption in liters/lap, excluding reserve |
| `estimated_finish_fuel` | Available fuel minus projected consumption, in liters |
| `safety_fuel_required` | Safety laps * consumption + additional safety liters |
| `total_fuel_required` | Projected consumption plus safety reserve, in liters |
| `fuel_margin` | Available fuel minus total requirement, in liters |
| `estimated_stint_duration` | Requested target duration in seconds, even for an unsafe projection |
| `status` | `SAFE` when unrounded fuel margin is >= 0; otherwise `UNSAFE` |

`safety_laps` defaults to 1.0 and can be fractional or zero. The independent
`safety_fuel_liters` defaults to zero and is additive. For a liters-only reserve,
set `--safety-laps 0 --safety-fuel-liters 3`.

Negative finish fuel or margin expresses a projected deficit; it is not clamped
to zero. A stint can have positive finish fuel and still be `UNSAFE` because it
does not preserve the configured reserve. Status is calculated before display
rounding. CLI exit code 0 means a valid calculation (including `UNSAFE`); invalid
arguments use exit code 2.

Inputs must be finite numbers; duration and lap time must be positive. Fuel,
consumption, and reserves may be zero but not negative. Invalid or missing inputs
raise `ValueError`; an analyzer average of `None` must not be replaced with zero.
Pass `analyzer.average_consumption` or `analyzer.rolling_average()` as consumption
once valid lap history exists. Average lap time is supplied separately.

This projection assumes constant average pace and consumption for the target
duration. It does not round up to whole race laps or include a final lap after
the timer, pit time, formation laps, or changing conditions. Account for extra
fuel using the configurable reserve. No telemetry integration is required.

### Setup and tests

In an isolated environment, with `python` pointing to your chosen interpreter:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

There are no runtime dependencies. Tests import from `src` via `tests/conftest.py`;
an editable install is optional (`python -m pip install -e .`). Package metadata
lives in `setup.py`, and pytest configuration lives in `pytest.ini`, since the
Python 3.3 toolchain predates modern `pyproject.toml` configuration.

Python 3.3.5 requires pip 9.0.3 (including for requirement markers) and the legacy
test dependencies selected in `requirements-dev.txt`. Newer Python environments
use compatible newer tooling. A passing test on a newer interpreter does not
replace validation on Python 3.3.5.

Type hints use type comments, avoiding a dependency on `typing` or newer Python
syntax. PySide6 is not compatible with Python 3.3.5; any future PySide6 desktop
UI must run in a separate modern Python process or require a revised target.
No GUI framework, pandas, or database dependency is installed by this scaffold.
