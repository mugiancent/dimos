"""Core type definitions and data structures for dimos."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class DimType(Enum):
    """Supported dimension types for dimensional arrays."""

    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    CHANNEL = "channel"
    BATCH = "batch"
    FEATURE = "feature"
    CUSTOM = "custom"


@dataclass
class Dimension:
    """Represents a single named dimension with optional metadata."""

    name: str
    size: Optional[int] = None  # None means dynamic/unknown
    dim_type: DimType = DimType.CUSTOM
    units: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        size_str = str(self.size) if self.size is not None else "?"
        return f"Dimension({self.name!r}, size={size_str}, type={self.dim_type.value})"

    def is_compatible(self, other: "Dimension") -> bool:
        """Check if two dimensions are compatible (same name and compatible sizes)."""
        if self.name != other.name:
            return False
        if self.size is not None and other.size is not None:
            return self.size == other.size
        return True


@dataclass
class DimSpec:
    """Specification for a set of dimensions describing a tensor shape."""

    dims: List[Dimension]

    def __post_init__(self) -> None:
        names = [d.name for d in self.dims]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate dimension names in spec: {names}")

    @property
    def names(self) -> List[str]:
        return [d.name for d in self.dims]

    @property
    def shape(self) -> Tuple[Optional[int], ...]:
        return tuple(d.size for d in self.dims)

    @property
    def ndim(self) -> int:
        return len(self.dims)

    def __getitem__(self, name: str) -> Dimension:
        for d in self.dims:
            if d.name == name:
                return d
        raise KeyError(f"Dimension {name!r} not found in spec")

    def __contains__(self, name: str) -> bool:
        return any(d.name == name for d in self.dims)

    def __repr__(self) -> str:
        return f"DimSpec({self.dims})"


# Convenience type alias for raw shape tuples
ShapeLike = Union[Tuple[int, ...], List[int]]

# Type for dimension name or index references
DimRef = Union[str, int]
