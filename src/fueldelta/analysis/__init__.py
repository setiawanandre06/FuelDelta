"""Fuel consumption analysis independent of telemetry access and UI."""

from .fuel_consumption import FuelConsumptionAnalyzer
from .pace_fuel import PaceFuelAnalyzer

__all__ = ["FuelConsumptionAnalyzer", "PaceFuelAnalyzer"]
