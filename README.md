# FuelDelta

A Python 3.3.5 project that will read Assetto Corsa telemetry and coach
drivers to save fuel while minimizing lap-time loss. This is an initial
scaffold only: telemetry integration, calculations, and a UI are not implemented.

## Layout

- `src/fueldelta/telemetry`: telemetry access and normalization.
- `src/fueldelta/analysis`: fuel consumption analysis.
- `src/fueldelta/strategy`: race fuel planning and coaching calculations.
- `src/fueldelta/models`: shared data models.
- `src/fueldelta/ui`: presentation only.
- `tests`: pytest tests.

## Development

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
