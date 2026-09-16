"""Basic verification of package discovery and the project layout."""

import importlib

import fueldelta


def test_project_packages_import():
    # type: () -> None
    assert fueldelta.__version__ == "0.1.0"
    for name in ("telemetry", "analysis", "strategy", "models", "ui"):
        module_name = "fueldelta." + name
        assert importlib.import_module(module_name).__name__ == module_name
