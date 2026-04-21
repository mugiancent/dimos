"""Unit conversion utilities for dimos.

Provides functions to convert Quantity instances between compatible units,
and to decompose compound units into base SI dimensions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dimos.units import lookup, Unit

if TYPE_CHECKING:
    from dimos.quantity import Quantity


class ConversionError(Exception):
    """Raised when a unit conversion is not possible."""


def _conversion_factor(from_unit: Unit, to_unit: Unit) -> float:
    """Compute the multiplicative factor to convert *from_unit* to *to_unit*.

    Both units must be dimensionally compatible (same :class:`~dimos.types.Dimension`).

    Parameters
    ----------
    from_unit:
        The source unit.
    to_unit:
        The target unit.

    Returns
    -------
    float
        Factor *f* such that ``value_in_from * f == value_in_to``.

    Raises
    ------
    ConversionError
        If the units have incompatible dimensions.
    """
    if not from_unit.dimension.is_compatible(to_unit.dimension):
        raise ConversionError(
            f"Cannot convert '{from_unit.symbol}' ({from_unit.dimension}) "
            f"to '{to_unit.symbol}' ({to_unit.dimension}): incompatible dimensions."
        )

    # Both units store a scale relative to the SI base for their dimension.
    # factor = from_scale / to_scale
    return from_unit.scale / to_unit.scale


def convert(quantity: "Quantity", target: str | Unit) -> "Quantity":
    """Convert *quantity* to *target* units.

    Parameters
    ----------
    quantity:
        The :class:`~dimos.quantity.Quantity` to convert.
    target:
        Either a :class:`~dimos.units.Unit` instance or a unit symbol string
        (e.g. ``"km"`` or ``"°F"``).

    Returns
    -------
    Quantity
        A new :class:`~dimos.quantity.Quantity` expressed in *target* units.

    Raises
    ------
    ConversionError
        If the conversion is not dimensionally valid.
    KeyError
        If *target* is a string that cannot be found in the unit registry.

    Examples
    --------
    >>> from dimos.quantity import Quantity
    >>> from dimos.convert import convert
    >>> d = Quantity(1.0, "km")
    >>> convert(d, "m")
    Quantity(1000.0, m)
    """
    # Lazy import to avoid circular dependency
    from dimos.quantity import Quantity

    if isinstance(target, str):
        to_unit = lookup(target)
    else:
        to_unit = target

    from_unit = quantity.unit
    factor = _conversion_factor(from_unit, to_unit)

    # Handle units with an offset (e.g. Celsius <-> Kelvin)
    new_magnitude = quantity.magnitude * factor
    if hasattr(from_unit, "offset") and from_unit.offset != 0.0:
        new_magnitude += from_unit.offset
    if hasattr(to_unit, "offset") and to_unit.offset != 0.0:
        new_magnitude -= to_unit.offset

    return Quantity(new_magnitude, to_unit)


def is_convertible(from_unit: str | Unit, to_unit: str | Unit) -> bool:
    """Return *True* if *from_unit* and *to_unit* are dimensionally compatible.

    Parameters
    ----------
    from_unit, to_unit:
        Unit instances or symbol strings.
    """
    if isinstance(from_unit, str):
        from_unit = lookup(from_unit)
    if isinstance(to_unit, str):
        to_unit = lookup(to_unit)
    return from_unit.dimension.is_compatible(to_unit.dimension)
