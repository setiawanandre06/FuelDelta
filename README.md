# FuelDelta

A Python 3.3.5 project that will read Assetto Corsa telemetry and coach
drivers to save fuel while minimizing lap-time loss. The internal telemetry
model and a fake source are available. Assetto Corsa integration, fuel analysis,
and a UI are not implemented.

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
