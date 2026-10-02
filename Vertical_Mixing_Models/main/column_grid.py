"""
Column grid specification for 1D ocean column model.

Provides immutable grid structure following MITgcm conventions:
- Depth negative downward (surface near 0, increasing depth is more negative)
- Cell thickness always positive

Also owns the shared z-coordinate input guard `validate_zcoordinate_geometry`
(1DMIX-072 for KPP, shared with GGL90 under 1DMIX-073): both schemes call it as
step 0 of their `compute_mixing`, so a column that cannot be a metres-scale
z-coordinate column (e.g. a pressure-coordinate grid in Pa) is rejected instead
of returning wrong values.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np


# Upper bound on any |depth|, total column thickness or single cell thickness
# that this port accepts as a metres-scale z-coordinate column [m].  The deepest
# point of the real ocean (Challenger Deep, Mariana Trench) is ~10,935 m, so no
# physical z-coordinate ocean column exceeds 11,000 m.  Every geometry this repo
# feeds the port (all KPP and GGL90 MITgcm captures, all six scenario grids, every
# test fixture that calls ``KPPDriver.compute_mixing`` or
# ``GGL90Driver.compute_mixing``) has max |depth| <= 5,450 m (1DMIX-072 evidence:
# devel-loop/loop_state/bob-1DMIX-072-evidence.md; 1DMIX-073 evidence:
# devel-loop/loop_state/bob-1DMIX-073-evidence.md), while the pressure-coordinate
# capture ``global_ocean.cs32x15`` (buoyancyRelation='OCEANICP', rC/rF/drF in Pa,
# identical grid in the KPP and GGL90 captures) has max |depth| = 4.9e7 and cell
# thicknesses up to 7.1e6.
MAX_ZCOORD_EXTENT_M = 11000.0


def validate_zcoordinate_geometry(depth: np.ndarray, cell_thickness: np.ndarray,
                                  scheme: str = "KPP/GGL90") -> None:
    """Reject column geometry that cannot be a metres-scale z-coordinate column.

    Pure input pre-check (1DMIX-072 for KPP; shared with GGL90 under 1DMIX-073):
    raises ``ValueError`` and otherwise returns ``None`` without touching,
    copying or altering any array, so it cannot change a computed value for
    valid input.  It exists because this port has no ``coordFac``/
    ``usingPCoords`` handling (MITgcm's ``pkg/kpp`` has none either; MITgcm's
    ``pkg/ggl90`` does, which the port does not reproduce): pressure-coordinate
    geometry (``rC``/``rF``/``drF`` in Pa, ~1e5-1e7) fed in as metres used to
    return silent NaN (KPP, ``swfrac``'s ``exp(-z/d)``) or finite wrong values
    (GGL90: mixing length up to 1.4e7 m) instead of being rejected.
    Pressure-coordinate support is permanently out of scope (1DMIX-040;
    ``docs/model_contract.md`` "z-coordinates only"), so the correct behaviour is
    explicit rejection.

    Checks, each naming the offending quantity and value:
      1. ``depth`` and ``cell_thickness`` finite.
      2. ``cell_thickness`` strictly positive (zero/negative-thickness cells are
         invalid input per the project profile).
      3. ``depth`` <= 0 everywhere (cell-centre depth, negative downward, the
         ``ColumnGrid`` convention; ``depth[0] == 0`` is allowed because some
         fixtures place the first node at the surface).  A positive depth is
         how a pressure-coordinate grid (``p`` in Pa, positive) presents.
      4. ``max|depth|``, ``sum(cell_thickness)`` and ``max(cell_thickness)`` each
         <= ``MAX_ZCOORD_EXTENT_M`` (11,000 m).

    Deliberately NOT checked: that ``depth`` equals the cumulative-thickness cell
    centres.  That holds for every capture and scenario grid, but several
    existing fixtures pass ``linspace(0, -H, nz)`` depths with ``H/nz`` thicknesses,
    and ice-shelf column slices start below index 0, so it would reject valid
    input.  Likewise not checked (known gap): that ``depth`` is monotonic or free
    of duplicate values.  Magnitudes in dbar (1 dbar ~ 1 m) are indistinguishable
    from metres by size and are not detected here.

    Parameters
    ----------
    depth : array-like
        Cell-centre depths, negative downward [m].
    cell_thickness : array-like
        Cell thicknesses [m], positive.
    scheme : str, optional
        Name of the calling scheme, used only in the error text (the callers pass
        ``"KPP"`` and ``"GGL90"``).  The default is the neutral ``"KPP/GGL90"``
        for direct calls.

    Raises
    ------
    ValueError
        If any check fails.
    """
    reason = (
        f"{scheme} supports z-coordinate (metres) columns only; pressure-coordinate "
        "(OCEANICP/usingPCoords, grid in Pa) input is permanently unsupported "
        "(1DMIX-040, docs/model_contract.md 'z-coordinates only')"
    )
    d = np.asarray(depth, dtype=np.float64)
    dz = np.asarray(cell_thickness, dtype=np.float64)
    if not (np.all(np.isfinite(d)) and np.all(np.isfinite(dz))):
        raise ValueError(
            f"{scheme} geometry must be finite: got {int(np.sum(~np.isfinite(d)))} non-finite "
            f"depth value(s) and {int(np.sum(~np.isfinite(dz)))} non-finite cell_thickness "
            f"value(s). {reason}"
        )
    if np.any(dz <= 0.0):
        raise ValueError(
            f"{scheme} cell_thickness must be strictly positive: got min(cell_thickness)="
            f"{float(dz.min()):.6g}. {reason}"
        )
    if np.any(d > 0.0):
        raise ValueError(
            f"{scheme} depth must be negative downward (<= 0 [m]): got max(depth)="
            f"{float(d.max()):.6g}. A positive-valued depth is how a pressure-coordinate "
            f"grid (Pa) presents. {reason}"
        )
    for name, value in (
        ("max|depth|", float(np.max(np.abs(d)))),
        ("sum(cell_thickness)", float(dz.sum())),
        ("max(cell_thickness)", float(dz.max())),
    ):
        if value > MAX_ZCOORD_EXTENT_M:
            raise ValueError(
                f"{scheme} {name}={value:.6g} exceeds the {MAX_ZCOORD_EXTENT_M:g} m maximum for a "
                f"z-coordinate ocean column (deepest ocean point ~10,935 m); this geometry "
                f"looks like Pa- or otherwise non-metre-scaled. {reason}"
            )


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
