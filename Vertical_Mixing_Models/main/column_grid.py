"""
Column grid specification for 1D ocean column model.

Provides immutable grid structure following MITgcm conventions:
- Depth negative downward (surface near 0, increasing depth is more negative)
- Cell thickness always positive
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass(frozen=True)
class ColumnGrid:
    """
    Immutable vertical grid specification for 1D column model.

    Attributes:
        depth: Cell center depths, negative downward [m], shape (nz,)
        cell_thickness: Layer thicknesses (drF) [m], shape (nz,)
    """
    depth: np.ndarray
    cell_thickness: np.ndarray

    def __post_init__(self):
        if len(self.depth) != len(self.cell_thickness):
            raise ValueError(
                f"Depth and cell_thickness must have same length: "
                f"{len(self.depth)} vs {len(self.cell_thickness)}"
            )
        if np.any(self.cell_thickness <= 0):
            raise ValueError("Cell thickness must be positive")

        object.__setattr__(self, 'depth', np.array(self.depth, dtype=np.float64))
        object.__setattr__(self, 'cell_thickness', np.array(self.cell_thickness, dtype=np.float64))

    @classmethod
    def from_drF(cls, drF: np.ndarray) -> 'ColumnGrid':
        """
        Build grid from layer thicknesses following MITgcm convention.

        Args:
            drF: Layer thicknesses [m], shape (nz,), all positive

        Returns:
            ColumnGrid with computed depths

        Example:
            >>> grid = ColumnGrid.from_drF([10.0, 10.0, 10.0])
            >>> grid.depth
            array([ -5., -15., -25.])
        """
        drF = np.asarray(drF, dtype=np.float64)

        faces = np.zeros(len(drF) + 1)
        faces[1:] = -np.cumsum(drF)

        depth = 0.5 * (faces[:-1] + faces[1:])

        return cls(depth=depth, cell_thickness=drF)

    @property
    def nz(self) -> int:
        """Number of vertical levels."""
        return len(self.depth)

    @property
    def z_positive_up(self) -> np.ndarray:
        """
        Vertical coordinate with positive upward convention (for GGL90).

        `depth` is already stored negative-downward (surface near 0,
        increasing depth is more negative) -- i.e. it is ALREADY a proper
        z-positive-up coordinate (shallower cells have larger/less-negative
        values). This property is therefore just an alias for `depth`; do
        NOT negate it again here, or z-ordering flips (shallow < deep
        instead of shallow > deep), silently inverting the sign of any N²/
        shear computed from it.

        Returns:
            Height coordinate [m], shape (nz,), positive upward
        """
        return self.depth

    @property
    def total_depth(self) -> float:
        """Total water column depth [m], always positive."""
        return float(np.sum(self.cell_thickness))

    @property
    def interfaces(self) -> np.ndarray:
        """
        Interface depths (cell faces), negative downward [m], shape (nz+1,).

        interfaces[0] = surface (0.0)
        interfaces[k] = interface between cells k-1 and k
        interfaces[nz] = bottom
        """
        faces = np.zeros(self.nz + 1)
        faces[1:] = -np.cumsum(self.cell_thickness)
        return faces

    def __repr__(self) -> str:
        return (
            f"ColumnGrid(nz={self.nz}, "
            f"total_depth={self.total_depth:.1f}m, "
            f"top_layer={self.cell_thickness[0]:.1f}m)"
        )
