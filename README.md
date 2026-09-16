# FuelDelta

A Python 3.3.5 project that will read Assetto Corsa telemetry and coach
drivers to save fuel while minimizing lap-time loss. The internal telemetry
model, a fake source, a fuel consumption analyzer, and a command-line stint
calculator, an ongoing-stint fuel budget engine, and a read-only Assetto Corsa
shared-memory adapter, CSV session recorder, and repeatable offline replay are
available. A graphical UI is not implemented.

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

### Fuel budget engine

`FuelBudgetEngine` evaluates whether current consumption can reach the stint
target and calculates the maximum affordable consumption. It uses actual fuel,
remaining time, average pace, and average fuel/lap. Starting fuel is not required:
the predictive budget is recalculated from the current tank, including after
refueling, rather than extrapolated linearly from the initial tank.

```python
from fueldelta.strategy import FuelBudgetEngine

engine = FuelBudgetEngine(target_duration_seconds=3600, safety_laps=0)
budget = engine.evaluate(
    remaining_fuel_liters=77.0,
    elapsed_seconds=1200.0,
    average_lap_seconds=72.5,
    consumption_liters_per_lap=2.42,
)
print(budget.status)                # INSUFFICIENT_FUEL
print(budget.required_consumption)  # approximately 2.326 L/lap
print(budget.need_to_save)          # approximately 0.094 L/lap
```

Use an analyzer's valid `rolling_average()` or `average_consumption` for current
consumption. Missing averages (`None`) raise `ValueError`, never a false safe
result. A known zero consumption is supported. The engine keeps configuration
only; call `evaluate` again as fuel, elapsed time, pace, or consumption changes.
Elapsed time is relative to this stint; callers reset it for a new stint and
must supply trustworthy averages after invalid laps or a session restart.

Command-line example from the project root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m fueldelta.ui.budget_cli --fuel 77 --minutes 60 --elapsed-minutes 20 --lap-time 72.5 --consumption 2.42 --safety-laps 0
```

```text
FUEL BUDGET
Remaining fuel:       77.00 L
Laps remaining:       33.10
Required fuel:        80.11 L
Delta:                -3.11 L
Projected finish:     -3.11 L
Safety reserve:       0.00 L
Current consumption:  2.420 L/lap
Required consumption: 2.326 L/lap
Need to save:         0.094 L/lap
Status:               INSUFFICIENT_FUEL
Current consumption will not reach the target duration.
```

For remaining time `T`, lap time `t`, current consumption `c`, available fuel `F`,
safety laps `s`, and fixed reserve liters `r`:

- Predicted laps remaining `L = T / t` (fractional laps).
- Required fuel `= (L + s) * c + r`, including reserve.
- Delta `= F - required fuel`; negative means behind the predictive budget.
- Projected finish fuel `= F - L * c`, excluding reserve.
- Required consumption `= (F - r) / (L + s)`, the maximum affordable liters/lap.
- Need to save `= max(0, c - required consumption)`.

Safety defaults match the stint calculator: `safety_laps=1.0` and
`safety_fuel_liters=0.0`, independently configurable and additive. The example
explicitly disables reserve. Safety laps are valued at the current consumption
for the projection and at the proposed reduced consumption for the saving target.
If fixed reserve exceeds available fuel, `required_consumption` and `need_to_save`
are `None`, and `can_meet_budget_by_saving` is false: even zero consumption cannot
fund that reserve. This flag describes arithmetic feasibility, not whether a
driver can physically achieve the proposed consumption or maintain the same pace.

The immutable `fueldelta.models.FuelBudget` result includes fuel, remaining time,
lap estimate, consumption targets, `can_finish_target`, and these statuses:

| Status | Meaning |
| --- | --- |
| `ON_BUDGET` | Current consumption covers the target and reserve |
| `INSUFFICIENT_FUEL` | Current consumption cannot reach the target duration |
| `BELOW_RESERVE` | Target is reachable, but configured reserve is not covered |
| `TARGET_REACHED` | Target time has elapsed; no future driving is budgeted |

At/after the target, remaining time/laps/required fuel/reserve and saving are zero,
projected finish and delta equal actual fuel, and required consumption is `None`.
`can_finish_target` is then true only in the sense that no future driving remains;
the engine does not infer historical success. Status uses unrounded values, and
negative projections express deficits. Invalid values raise `ValueError`; CLI
input errors exit with code 2, while all valid budgets exit with code 0.

Like the stint calculator, this assumes constant average pace and consumption,
without whole-lap rounding or a final lap after the timer. Fuel saving may change
pace; reevaluate with updated averages. There is no AC-specific data access or
business logic in the command-line presentation.

### Live Assetto Corsa telemetry (Windows)

Start original Assetto Corsa, load a Practice/Race session, and enter the car
with the game unpaused. Run this externally from the FuelDelta directory:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m fueldelta.ui.telemetry_cli
```

Use `--samples 1` for a single snapshot, or `--interval 0.2 --samples 10` for
ten snapshots. Ctrl+C stops the reader. This does not require enabling an in-game
Python app. Use a normal Windows Python installation with ctypes available.

The CLI prints connection confirmation only after a valid live snapshot, then
car/track identifiers, fuel, speed, pedals, RPM, and the one-based lap number.
Names come directly from metadata (for example `bmw_m4_gt3`), not a friendly-name
catalog. Exit code 1 means unavailable telemetry; 2 means invalid CLI arguments.
On pause, replay, missing mappings, or stale physics, resume the driving session
and rerun the CLI. It deliberately stops rather than displaying stale readings.

```python
from fueldelta.telemetry import AssettoCorsaTelemetrySource, TelemetryUnavailable

try:
    with AssettoCorsaTelemetrySource() as source:
        sample = source.read()  # ordinary TelemetrySample
        print(source.car, source.track, sample.fuel_liters)
except TelemetryUnavailable as error:
    print(error)
```

The adapter has no fuel calculation logic. A consuming loop can pass samples to
`FuelConsumptionAnalyzer.update`; on unavailable data it must signal
`analyzer.update(None)` instead of reusing the last sample. Lap validity is still
external; this adapter does not infer it from penalties or invent an AC field.

The packed prefixes follow the supplied
[AC sim_info reference](https://github.com/ac-custom-shaders-patch/acc-extension-apps/blob/master/apps/python/AccExtHelper/sim_info.py).
Only necessary prefixes are read: physics 32 bytes, graphics 252 bytes, static
200 bytes. Integers/floats are 32-bit, packing is 4 bytes, and text uses explicit
UTF-16LE code units. These are original AC layouts, not ACC/EVO layouts.

| AC value | Internal value |
| --- | --- |
| physics `fuel`, `speedKmh` | `fuel_liters`, `speed_kmh` |
| physics `gas`, `brake`, `rpms` | `throttle`, `brake`, `rpm` |
| physics `gear - 1` | `gear` (-1 reverse, 0 neutral, 1+ forward) |
| graphics `completedLaps + 1` | `lap_number` |
| graphics `iCurrentTime` | `lap_time_ms` |
| graphics `normalizedCarPosition` | `normalized_position` (1.0 wraps to 0.0) |
| static `carModel`, `track` | source metadata |

Connection uses ctypes with Windows `OpenFileMappingW` and
[`MapViewOfFile`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile)
in read-only mode. Unlike a create-or-open named mmap, it cannot create an empty
AC mapping when the game is absent. Handles/views are released by `close()` or
the context manager. Nothing connects at import time.

Timestamp is host monotonic time since the reader's first accepted observation,
not true elapsed race time. A metadata/session change, lap counter rollback, or
same-lap timer rollback starts a new observation epoch and increments
`session_generation`. Consumers should reset analyzer/stint state when that
generation changes. AC exposes no unique session ID in the prefixes used here;
not every restart can be detected. Reconnect on explicit game/session changes.
Host time includes pauses; do not use it directly as budget-engine stint elapsed
time without an application-level active-session clock.

The reader retries five times if consecutive copies differ. This reduces torn
reads but cannot make separately published pages atomic. Physics packet IDs
unchanged for 2 seconds are stale (`stale_seconds` is configurable). Repeated
packets before that timeout can return repeated observations. Status must be
live, required metadata must be populated, and mapped numeric fields must be
valid. A closed game may leave an existing view readable briefly, so this is
not proof that the producer process remains alive.

Offline tests verify byte offsets, field normalization, stale/non-live data,
cleanup, and a real Windows mapping under a unique test name. They never write
to AC mappings. A live smoke test on this workstation read six consecutive
samples over 2.5 seconds from `rss_gtm_lanzo_v10` at `rt_sebring`: about 49.99 L,
1500 RPM, lap 1, stationary. This verifies a live connection and updating physics;
driving, lap transitions, and game restarts still need in-game validation.

### Session recording and offline replay

With AC live and unpaused, record at 10 Hz (20 Hz is also supported by the CLI):

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m fueldelta.ui.record_cli --target-minutes 60 --hz 10
```

Ctrl+C finalizes the recording. `--seconds 30` limits the capture to approximately
30 seconds; `--output data` selects the parent directory. The target duration is
metadata for the planned stint, not an automatic capture stop. Capture frequency
is best effort, not a hard real-time guarantee; slow reads do not generate a burst
of backfilled samples.

Each capture creates a new directory, for example:

```text
data/2026-09-20_spa_bmw_m4_gt3_<unique-id>/
    telemetry.csv
    session.json
```

The date is UTC. Names are sanitized and a unique suffix prevents overwriting
another session on the same day. Generated recordings are ignored by Git.
Metadata contains `schema_version: 1`, raw car/track identifiers, `initial_fuel`,
`target_duration_minutes`, configured `sample_rate_hz`, UTC creation time, sample
count, first/last source timestamps, status, and stop reason. Initial fuel is
measured from the first recorded sample, not entered manually.

CSV version 1 stores every internal field, with no display rounding:

```text
timestamp,fuel_liters,speed_kmh,throttle,brake,rpm,gear,lap_number,lap_time_ms,normalized_position
```

Lap numbers remain one-based and gear retains the internal -1/0/1+ convention.
Timestamps are preserved from the source; for AC this is the reader observation
epoch, not absolute race time. A capture can start mid-lap; the analyzer still
discards that partial lap. Recording writes every sample passed to `record()`;
`capture_session()` controls source polling frequency separately.

No game is needed to replay a directory (or its `telemetry.csv`):

```python
from fueldelta.analysis import FuelConsumptionAnalyzer
from fueldelta.telemetry import ReplayTelemetrySource

path = "data/2026-09-20_spa_bmw_m4_gt3_<unique-id>"  # use your actual directory
with ReplayTelemetrySource(path) as source:
    for run in range(3):
        source.reset()
        analyzer = FuelConsumptionAnalyzer()
        while True:
            try:
                sample = source.read()
            except StopIteration:
                break
            analyzer.update(sample)
        print(run + 1, analyzer.consumption_history, analyzer.average_consumption)
```

Replay is deterministic and unpaced: `read()` returns the next sample immediately
while preserving its recorded timestamp. `reset()` rewinds an open source;
opening another source creates an independent replay. EOF raises `StopIteration`.
Invalid headers/schema, malformed rows, invalid field values, or backwards
timestamps raise `ValueError`; row errors identify the CSV line. A failed replay
must be reset or repaired, so corrupted data is never silently skipped. Header
aliases such as `fuel`/`lap` from arbitrary third-party CSVs are not supported.

The generic `SessionRecorder` accepts `TelemetrySample` objects and can also
record fake/custom sources. Neither persistence nor replay performs fuel math.
`capture_session` uses source `car`/`track` metadata and, when available,
`session_generation` to stop before a new epoch is mixed into the recording.
On pause, stale/unavailable telemetry, or an I/O error, capture stops; restart the
command to create a new session file. No missing samples are fabricated. A normal
stop or exception closes the CSV and finalizes metadata; every CSV row is flushed.
Abrupt process termination or power loss may leave incomplete trailing data and
metadata with status `recording` and outdated counts. CSV data remains authoritative;
this is not a transactional or power-loss-proof recorder.

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
