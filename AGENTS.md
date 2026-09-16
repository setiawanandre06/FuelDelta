# Fuel Delta

## Goal

Build a Python desktop application that reads Assetto Corsa
telemetry and provides real-time fuel-saving coaching.

## Technology

- Python 3.3.5
- pytest
- SQLite
- PySide6
- pandas only when useful
- type hints
- no unnecessary dependencies

## Architecture

Keep these concerns separate:

- telemetry: reading Assetto Corsa data
- analysis: calculating fuel consumption
- strategy: race fuel calculations
- models: shared data models without UI or telemetry-access dependencies
- ui: presentation only

Do not put business logic inside UI code.

Use a src layout with importable code under `src/fueldelta` and tests under
`tests`. Keep package imports free of telemetry connections and UI startup.
The initial scaffold must not implement Assetto Corsa integration.

## Development Rules

- Write tests for calculation logic.
- Do not modify third-party libraries.
- Prefer small functions.
- Do not invent telemetry fields.
- Document assumptions about Assetto Corsa telemetry.
- Run pytest after modifying calculation logic.
- Keep runtime code compatible with Python 3.3.5; use type comments for hints.
- Do not use f-strings, variable annotations, dataclasses, or the typing module.
- Keep package metadata in setup.py and test configuration in pytest.ini.
- Run tests with `python -m pytest`; document the interpreter used.
- Add dependencies only when needed. SQLite is in the standard library.
- PySide6 requires modern Python; defer it to a separate modern UI process
  or an explicitly revised runtime target. Do not install it in Python 3.3.5.

## Git

Keep commits small and focused.
Do not modify unrelated files.
