"""Quantity: a numeric value paired with a unit and optional uncertainty.

This module provides the ``Quantity`` class, which is the primary user-facing
object in *dimos*.  A Quantity combines a scalar (or array-like) magnitude with
a :class:`~dimos.units.Unit` so that arithmetic and comparisons are
dimension-aware.

Example usage::

    >>> from dimos.quantity import Quantity
    >>> from dimos.units import lookup
    >>> m = lookup("m")
    >>> s = lookup("s")
    >>> d = Quantity(100, m)
    >>> t = Quantity(9.58, s)
    >>> speed = d / t
    >>> print(speed)
    10.438... m s⁻¹
"""

from __future__ import annotations

import math
import operator
from typing import Union

from dimos.units import Unit

# Numeric types accepted as magnitudes
_Numeric = Union[int, float, complex]


class Quantity:
    """A magnitude with an associated :class:`~dimos.units.Unit`.

    Parameters
    ----------
    magnitude:
        The numeric value of the quantity.
    unit:
        The :class:`~dimos.units.Unit` that describes the dimensions and scale
        of the quantity.
    """

    __slots__ = ("_magnitude", "_unit")

    def __init__(self, magnitude: _Numeric, unit: Unit) -> None:
        if not isinstance(unit, Unit):
            raise TypeError(
                f"unit must be a Unit instance, got {type(unit).__name__!r}"
            )
        self._magnitude: _Numeric = magnitude
        self._unit: Unit = unit

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def magnitude(self) -> _Numeric:
        """The bare numeric value."""
        return self._magnitude

    @property
    def unit(self) -> Unit:
        """The associated :class:`~dimos.units.Unit`."""
        return self._unit

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return f"Quantity({self._magnitude!r}, {self._unit!r})"

    def __str__(self) -> str:
        return f"{self._magnitude} {self._unit}"

    # ------------------------------------------------------------------
    # Arithmetic helpers
    # ------------------------------------------------------------------

    def _check_compatible(self, other: "Quantity") -> None:
        """Raise :exc:`ValueError` if *other* has incompatible dimensions."""
        if not self._unit.dimension.is_compatible(other._unit.dimension):
            raise ValueError(
                f"Incompatible dimensions: {self._unit.dimension} vs "
                f"{other._unit.dimension}"
            )

    def _to_base(self) -> _Numeric:
        """Return the magnitude expressed in base-unit scale."""
        return self._magnitude * self._unit.scale

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __add__(self, other: "Quantity") -> "Quantity":
        if not isinstance(other, Quantity):
            return NotImplemented
        self._check_compatible(other)
        # Express both in *self*'s unit
        converted = other._to_base() / self._unit.scale
        return Quantity(self._magnitude + converted, self._unit)

    def __sub__(self, other: "Quantity") -> "Quantity":
        if not isinstance(other, Quantity):
            return NotImplemented
        self._check_compatible(other)
        converted = other._to_base() / self._unit.scale
        return Quantity(self._magnitude - converted, self._unit)

    def __mul__(self, other: object) -> "Quantity":
        if isinstance(other, Quantity):
            new_unit = self._unit * other._unit
            return Quantity(self._magnitude * other._magnitude, new_unit)
        if isinstance(other, (int, float, complex)):
            return Quantity(self._magnitude * other, self._unit)
        return NotImplemented

    def __rmul__(self, other: object) -> "Quantity":
        return self.__mul__(other)

    def __truediv__(self, other: object) -> "Quantity":
        if isinstance(other, Quantity):
            new_unit = self._unit / other._unit
            return Quantity(self._magnitude / other._magnitude, new_unit)
        if isinstance(other, (int, float, complex)):
            return Quantity(self._magnitude / other, self._unit)
        return NotImplemented

    def __rtruediv__(self, other: object) -> "Quantity":
        if isinstance(other, (int, float, complex)):
            new_unit = self._unit ** -1
            return Quantity(other / self._magnitude, new_unit)
        return NotImplemented

    def __pow__(self, exponent: Union[int, float]) -> "Quantity":
        return Quantity(self._magnitude ** exponent, self._unit ** exponent)

    def __neg__(self) -> "Quantity":
        return Quantity(-self._magnitude, self._unit)

    def __pos__(self) -> "Quantity":
        return Quantity(+self._magnitude, self._unit)

    def __abs__(self) -> "Quantity":
        return Quantity(abs(self._magnitude), self._unit)

    # ------------------------------------------------------------------
    # Comparisons  (same dimension required; converts to base scale)
    # ------------------------------------------------------------------

    def _cmp(self, other: "Quantity", op) -> bool:  # type: ignore[type-arg]
        if not isinstance(other, Quantity):
            return NotImplemented  # type: ignore[return-value]
        self._check_compatible(other)
        return op(self._to_base(), other._to_base())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quantity):
            return NotImplemented
        try:
            return self._cmp(other, operator.eq)
        except ValueError:
            return False

    def __lt__(self, other: "Quantity") -> bool:
        return self._cmp(other, operator.lt)

    def __le__(self, other: "Quantity") -> bool:
        return self._cmp(other, operator.le)

    def __gt__(self, other: "Quantity") -> bool:
        return self._cmp(other, operator.gt)

    def __ge__(self, other: "Quantity") -> bool:
        return self._cmp(other, operator.ge)

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to(self, target_unit: Unit) -> "Quantity":
        """Return an equivalent :class:`Quantity` expressed in *target_unit*.

        Parameters
        ----------
        target_unit:
            The :class:`~dimos.units.Unit` to convert into.  Must share the
            same dimension as the current unit.

        Returns
        -------
        Quantity
            A new :class:`Quantity` with the converted magnitude.

        Raises
        ------
        ValueError
            If *target_unit* has incompatible dimensions.
        """
        if not self._unit.dimension.is_compatible(target_unit.dimension):
            raise ValueError(
                f"Cannot convert {self._unit.dimension} to "
                f"{target_unit.dimension}"
            )
        new_magnitude = self._to_base() / target_unit.scale
        return Quantity(new_magnitude, target_unit)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def __hash__(self) -> int:  # needed because __eq__ is defined
        return hash((self._to_base(), self._unit.dimension))
