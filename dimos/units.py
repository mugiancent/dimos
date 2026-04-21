"""Physical unit definitions and conversions for dimos.

This module provides a registry of common physical units organized by
dimensional category (length, mass, time, etc.), along with conversion
factors to SI base units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from dimos.types import DimSpec, Dimension, DimType


@dataclass(frozen=True)
class Unit:
    """Represents a physical unit with its dimensional signature and SI conversion.

    Attributes:
        name: Human-readable unit name (e.g. "metre").
        symbol: Standard symbol (e.g. "m").
        dimensions: Dimensional signature of the unit.
        to_si: Multiplicative factor to convert this unit to the SI equivalent.
        offset: Additive offset applied *before* the scale factor (used for
                temperature conversions such as Celsius → Kelvin).
    """

    name: str
    symbol: str
    dimensions: DimSpec
    to_si: float = 1.0
    offset: float = 0.0

    def __repr__(self) -> str:  # noqa: D401
        return f"Unit({self.symbol!r}, dims={self.dimensions})"


# ---------------------------------------------------------------------------
# Dimensional signatures (SI base dimensions)
# ---------------------------------------------------------------------------

_LENGTH = {DimType.LENGTH: Dimension(DimType.LENGTH, 1)}
_MASS = {DimType.MASS: Dimension(DimType.MASS, 1)}
_TIME = {DimType.TIME: Dimension(DimType.TIME, 1)}
_CURRENT = {DimType.CURRENT: Dimension(DimType.CURRENT, 1)}
_TEMPERATURE = {DimType.TEMPERATURE: Dimension(DimType.TEMPERATURE, 1)}
_AMOUNT = {DimType.AMOUNT: Dimension(DimType.AMOUNT, 1)}
_LUMINOSITY = {DimType.LUMINOSITY: Dimension(DimType.LUMINOSITY, 1)}
_DIMENSIONLESS: DimSpec = {}

# Derived dimensional signatures
_AREA = {DimType.LENGTH: Dimension(DimType.LENGTH, 2)}
_VOLUME = {DimType.LENGTH: Dimension(DimType.LENGTH, 3)}
_VELOCITY = {
    DimType.LENGTH: Dimension(DimType.LENGTH, 1),
    DimType.TIME: Dimension(DimType.TIME, -1),
}
_ACCELERATION = {
    DimType.LENGTH: Dimension(DimType.LENGTH, 1),
    DimType.TIME: Dimension(DimType.TIME, -2),
}
_FORCE = {
    DimType.MASS: Dimension(DimType.MASS, 1),
    DimType.LENGTH: Dimension(DimType.LENGTH, 1),
    DimType.TIME: Dimension(DimType.TIME, -2),
}
_PRESSURE = {
    DimType.MASS: Dimension(DimType.MASS, 1),
    DimType.LENGTH: Dimension(DimType.LENGTH, -1),
    DimType.TIME: Dimension(DimType.TIME, -2),
}
_ENERGY = {
    DimType.MASS: Dimension(DimType.MASS, 1),
    DimType.LENGTH: Dimension(DimType.LENGTH, 2),
    DimType.TIME: Dimension(DimType.TIME, -2),
}

# ---------------------------------------------------------------------------
# Unit registry
# ---------------------------------------------------------------------------

#: Maps symbol → Unit for fast lookup.
REGISTRY: Dict[str, Unit] = {}


def _reg(*units: Unit) -> None:
    """Register one or more units into the global REGISTRY."""
    for u in units:
        REGISTRY[u.symbol] = u


# --- Length ---
_reg(
    Unit("metre", "m", _LENGTH),
    Unit("kilometre", "km", _LENGTH, to_si=1_000.0),
    Unit("centimetre", "cm", _LENGTH, to_si=0.01),
    Unit("millimetre", "mm", _LENGTH, to_si=0.001),
    Unit("inch", "in", _LENGTH, to_si=0.0254),
    Unit("foot", "ft", _LENGTH, to_si=0.3048),
    Unit("mile", "mi", _LENGTH, to_si=1_609.344),
    Unit("nautical mile", "nmi", _LENGTH, to_si=1_852.0),
)

# --- Mass ---
_reg(
    Unit("kilogram", "kg", _MASS),
    Unit("gram", "g", _MASS, to_si=0.001),
    Unit("milligram", "mg", _MASS, to_si=1e-6),
    Unit("tonne", "t", _MASS, to_si=1_000.0),
    Unit("pound", "lb", _MASS, to_si=0.453_592_37),
    Unit("ounce", "oz", _MASS, to_si=0.028_349_523_125),
)

# --- Time ---
_reg(
    Unit("second", "s", _TIME),
    Unit("millisecond", "ms", _TIME, to_si=0.001),
    Unit("microsecond", "us", _TIME, to_si=1e-6),
    Unit("minute", "min", _TIME, to_si=60.0),
    Unit("hour", "h", _TIME, to_si=3_600.0),
    Unit("day", "d", _TIME, to_si=86_400.0),
)

# --- Temperature ---
_reg(
    Unit("kelvin", "K", _TEMPERATURE),
    Unit("celsius", "°C", _TEMPERATURE, to_si=1.0, offset=273.15),
    Unit("fahrenheit", "°F", _TEMPERATURE, to_si=5 / 9, offset=255.372_222),
)

# --- Force / Energy / Pressure ---
_reg(
    Unit("newton", "N", _FORCE),
    Unit("joule", "J", _ENERGY),
    Unit("kilojoule", "kJ", _ENERGY, to_si=1_000.0),
    Unit("pascal", "Pa", _PRESSURE),
    Unit("kilopascal", "kPa", _PRESSURE, to_si=1_000.0),
    Unit("bar", "bar", _PRESSURE, to_si=100_000.0),
    Unit("atmosphere", "atm", _PRESSURE, to_si=101_325.0),
)


def lookup(symbol: str) -> Optional[Unit]:
    """Return the :class:`Unit` registered under *symbol*, or ``None``."""
    return REGISTRY.get(symbol)


__all__ = ["Unit", "REGISTRY", "lookup"]
