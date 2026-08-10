"""
Column state container for 1D ocean column model.

Manages prognostic variables (T, S, U, V) and optional scheme-specific variables (e.g., TKE for GGL90).
"""

from dataclasses import dataclass, field
from typing import Dict
import numpy as np


@dataclass
class ColumnState:
    """
    Mutable state container for 1D column prognostic variables.

    Core fields (always present):
        theta: Potential temperature [°C], shape (nz,)
        salt: Salinity [psu], shape (nz,)
        u_vel: Zonal velocity [m/s], shape (nz,)
        v_vel: Meridional velocity [m/s], shape (nz,)

    Optional fields (scheme-specific):
        prognostic_vars: Dictionary of additional prognostic variables
                        e.g., {'tke': array} for GGL90
    """
    theta: np.ndarray
    salt: np.ndarray
    u_vel: np.ndarray
    v_vel: np.ndarray
    prognostic_vars: Dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self):
        self.theta = np.asarray(self.theta, dtype=np.float64)
        self.salt = np.asarray(self.salt, dtype=np.float64)
        self.u_vel = np.asarray(self.u_vel, dtype=np.float64)
        self.v_vel = np.asarray(self.v_vel, dtype=np.float64)

        nz = len(self.theta)
        if not (len(self.salt) == len(self.u_vel) == len(self.v_vel) == nz):
            raise ValueError(
                f"All core fields must have same length: "
                f"theta={len(self.theta)}, salt={len(self.salt)}, "
                f"u_vel={len(self.u_vel)}, v_vel={len(self.v_vel)}"
            )

        for name, var in self.prognostic_vars.items():
            if len(var) != nz:
                raise ValueError(
                    f"Prognostic variable '{name}' has length {len(var)}, "
                    f"expected {nz} to match core fields"
                )

    def validate(self, nz: int):
        """
        Validate that state dimensions match expected grid size.

        Args:
            nz: Expected number of vertical levels

        Raises:
            ValueError: If any field has incorrect size
        """
        if len(self.theta) != nz:
            raise ValueError(f"State has nz={len(self.theta)}, expected {nz}")

        fields_to_check = {
            'theta': self.theta,
            'salt': self.salt,
            'u_vel': self.u_vel,
            'v_vel': self.v_vel,
        }

        for name, field_arr in fields_to_check.items():
            if len(field_arr) != nz:
                raise ValueError(
                    f"Field '{name}' has length {len(field_arr)}, expected {nz}"
                )

        for name, var in self.prognostic_vars.items():
            if len(var) != nz:
                raise ValueError(
                    f"Prognostic variable '{name}' has length {len(var)}, expected {nz}"
                )

    def copy(self) -> 'ColumnState':
        """
        Create a deep copy of the state.

        Returns:
            New ColumnState with copied arrays
        """
        prognostic_copy = {
            name: var.copy() for name, var in self.prognostic_vars.items()
        }

        return ColumnState(
            theta=self.theta.copy(),
            salt=self.salt.copy(),
            u_vel=self.u_vel.copy(),
            v_vel=self.v_vel.copy(),
            prognostic_vars=prognostic_copy
        )

    @property
    def nz(self) -> int:
        """Number of vertical levels."""
        return len(self.theta)

    def __repr__(self) -> str:
        prog_vars_str = list(self.prognostic_vars.keys()) if self.prognostic_vars else []
        return (
            f"ColumnState(nz={self.nz}, "
            f"T_range=[{self.theta.min():.2f}, {self.theta.max():.2f}]°C, "
            f"S_range=[{self.salt.min():.2f}, {self.salt.max():.2f}]psu"
            f"{', prognostic=' + str(prog_vars_str) if prog_vars_str else ''})"
        )
