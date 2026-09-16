"""CLI input formats, output, and validation."""

import argparse

import pytest

from fueldelta.ui.cli import main, parse_lap_time


@pytest.mark.parametrize("value", ["78.5", "1:18.500"])
def test_cli_requested_example(value, capsys):
    assert main(["--fuel", "120", "--minutes", "60", "--lap-time", value,
                 "--consumption", "2.5"]) == 0
    output, errors = capsys.readouterr()
    assert "Projected laps:       45.86" in output
    assert "Projected fuel:       114.65 L" in output
    assert "Finish fuel:          5.35 L" in output
    assert "Safety reserve:       2.50 L" in output
    assert "Fuel margin:          2.85 L" in output
    assert "Status:               SAFE" in output
    assert errors == ""


def test_cli_reserve_can_be_configured(capsys):
    main(["--fuel", "120", "--minutes", "60", "--lap-time", "78.5",
          "--consumption", "2.5", "--safety-laps", "0",
          "--safety-fuel-liters", "6"])
    output, errors = capsys.readouterr()
    assert "Safety reserve:       6.00 L" in output
    assert "Status:               UNSAFE" in output


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1:60", "-1:20",
                                   "1:-2", "1:2:3", "abc", ""])
def test_bad_lap_time(value):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_lap_time(value)


def test_cli_invalid_input_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--fuel", "-1", "--minutes", "60", "--lap-time", "78.5",
              "--consumption", "2.5"])
    assert error.value.code == 2
    output, errors = capsys.readouterr()
    assert "fuel_liters" in errors
    assert "SAFE" not in output
