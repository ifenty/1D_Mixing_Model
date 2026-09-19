"""
Diagnostics manager for 1D column model.

Collects time-series snapshots and saves to compressed NPZ format.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np

from .column_grid import ColumnGrid
from .column_state import ColumnState
from .mixing_adapter import MixingOutput
from .eos import jmd95_eos


class DiagnosticsManager:
    """
    Manages collection and output of time-series diagnostics.

    Accumulates snapshots of state and mixing outputs, then saves to NPZ format.

    Args:
        grid: Column grid (for metadata)
        scheme_name: Name of mixing scheme (e.g., 'KPP', 'GGL90')
    """

    def __init__(self, grid: ColumnGrid, scheme_name: str, rho_const: float = 1029.0):
        self.grid = grid
        self.scheme_name = scheme_name
        self.rho_const = rho_const

        self.time: List[float] = []

        self.theta: List[np.ndarray] = []
        self.salt: List[np.ndarray] = []
        self.u_vel: List[np.ndarray] = []
        self.v_vel: List[np.ndarray] = []

        self.potential_density: List[np.ndarray] = []
        self.drho_dz: List[np.ndarray] = []
        self.shear_s2: List[np.ndarray] = []

        self.visc_az: List[np.ndarray] = []
        self.diff_kz_t: List[np.ndarray] = []
        self.diff_kz_s: List[np.ndarray] = []

        self.ghat: List[Optional[np.ndarray]] = []

        self.prognostic_vars: Dict[str, List[np.ndarray]] = {}

        self.scalar_diagnostics: Dict[str, List[Any]] = {}

    def _compute_density_diagnostics(
        self,
        theta: np.ndarray,
        salt: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute potential density and vertical density gradient.

        Potential density is evaluated at reference pressure 0 dbar.
        drho_dz is evaluated on the same interface indexing used by other
        top-of-cell fields (index 0 left at 0).
        """
        nz = self.grid.nz

        # Potential density referenced to the surface (0 dbar).
        rho_anom, _, _ = jmd95_eos(
            theta,
            salt,
            np.zeros(nz),
            rho_const=self.rho_const,
        )
        potential_density = rho_anom + self.rho_const

        # d(rho)/dz with z positive upward, matching N^2 sign convention.
        # grid.depth is ALREADY negative-downward, i.e. already a proper
        # z-positive-up coordinate (shallow > deep) -- do not negate it again
        # (see ColumnGrid.z_positive_up).
        z_up = self.grid.depth
        drho_dz = np.zeros(nz)
        for k in range(1, nz):
            drho_dz[k] = (
                (potential_density[k - 1] - potential_density[k])
                / (z_up[k - 1] - z_up[k])
            )

        return potential_density, drho_dz

    def _compute_shear_s2(
        self,
        u_vel: np.ndarray,
        v_vel: np.ndarray,
    ) -> np.ndarray:
        """Compute (du/dz)^2 + (dv/dz)^2 on interface indexing [s^-2]."""
        nz = self.grid.nz
        # grid.depth is already a proper z-positive-up coordinate -- see note
        # in _compute_density_diagnostics above.
        z_up = self.grid.depth
        shear_s2 = np.zeros(nz)
        for k in range(1, nz):
            du_dz = (u_vel[k - 1] - u_vel[k]) / (z_up[k - 1] - z_up[k])
            dv_dz = (v_vel[k - 1] - v_vel[k]) / (z_up[k - 1] - z_up[k])
            shear_s2[k] = du_dz * du_dz + dv_dz * dv_dz
        return shear_s2

    def save_snapshot(
        self,
        time: float,
        state: ColumnState,
        mix_output: Optional[MixingOutput] = None
    ):
        """
        Save snapshot of current state and mixing output.

        Args:
            time: Current time [s]
            state: Current state
            mix_output: Mixing output (None for initial condition)
        """
        self.time.append(time)

        self.theta.append(state.theta.copy())
        self.salt.append(state.salt.copy())
        self.u_vel.append(state.u_vel.copy())
        self.v_vel.append(state.v_vel.copy())

        potential_density, drho_dz = self._compute_density_diagnostics(
            state.theta, state.salt
        )
        self.potential_density.append(potential_density)
        self.drho_dz.append(drho_dz)
        self.shear_s2.append(self._compute_shear_s2(state.u_vel, state.v_vel))

        for var_name, var_array in state.prognostic_vars.items():
            if var_name not in self.prognostic_vars:
                self.prognostic_vars[var_name] = []
            self.prognostic_vars[var_name].append(var_array.copy())

        if mix_output is not None:
            self.visc_az.append(mix_output.visc_az.copy())
            self.diff_kz_t.append(mix_output.diff_kz_t.copy())
            self.diff_kz_s.append(mix_output.diff_kz_s.copy())

            if mix_output.ghat is not None:
                self.ghat.append(mix_output.ghat.copy())
            else:
                self.ghat.append(None)

            for diag_name, diag_value in mix_output.diagnostics.items():
                if diag_name not in self.scalar_diagnostics:
                    self.scalar_diagnostics[diag_name] = []
                self.scalar_diagnostics[diag_name].append(diag_value)

    def get_diagnostics(self) -> Dict[str, np.ndarray]:
        """
        Get all diagnostics as numpy arrays.

        Returns:
            Dictionary with all diagnostic timeseries
        """
        result = {
            'time_seconds': np.array(self.time),
            'theta': np.array(self.theta),
            'salt': np.array(self.salt),
            'u_vel': np.array(self.u_vel),
            'v_vel': np.array(self.v_vel),
            'potential_density': np.array(self.potential_density),
            'drho_dz': np.array(self.drho_dz),
            'shear_s2': np.array(self.shear_s2),
        }

        if self.visc_az:
            result['visc_az'] = np.array(self.visc_az)
            result['diff_kz_t'] = np.array(self.diff_kz_t)
            result['diff_kz_s'] = np.array(self.diff_kz_s)

        if any(g is not None for g in self.ghat):
            result['ghat'] = np.array([g if g is not None else np.zeros(self.grid.nz)
                                      for g in self.ghat])

        for var_name, var_list in self.prognostic_vars.items():
            result[var_name] = np.array(var_list)

        for diag_name, diag_list in self.scalar_diagnostics.items():
            diag_array = np.array(diag_list)
            result[diag_name] = diag_array

        return result

    def save_to_file(self, output_path: Path):
        """
        Save diagnostics to compressed NPZ file.

        Includes:
        - Time series of state variables
        - Time series of mixing coefficients
        - Scheme-specific diagnostics
        - Grid metadata

        Args:
            output_path: Path for output NPZ file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        diag_dict = self.get_diagnostics()

        diag_dict['depth'] = self.grid.depth
        diag_dict['cell_thickness'] = self.grid.cell_thickness
        diag_dict['scheme'] = self.scheme_name

        np.savez_compressed(output_path, **diag_dict)
