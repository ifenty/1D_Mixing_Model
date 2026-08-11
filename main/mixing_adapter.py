"""
Mixing scheme adapters for unified 1D column driver.

Provides abstract base class and concrete adapters for KPP and GGL90,
handling differences between diagnostic and prognostic mixing schemes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import numpy as np

from .column_state import ColumnState
from .column_grid import ColumnGrid


@dataclass
class MixingOutput:
    """
    Standardized output from mixing schemes.

    Required fields (all schemes must provide):
        visc_az: Vertical viscosity [m²/s], shape (nz,)
        diff_kz_t: Temperature diffusivity [m²/s], shape (nz,)
        diff_kz_s: Salinity diffusivity [m²/s], shape (nz,)

    Optional fields:
        ghat: Nonlocal transport coefficient [s/m²], shape (nz,) - KPP only
        updated_prognostic: Dict of updated prognostic variables - GGL90 returns {'tke': array}

    Diagnostics:
        diagnostics: Dict of scheme-specific diagnostic outputs
    """
    visc_az: np.ndarray
    diff_kz_t: np.ndarray
    diff_kz_s: np.ndarray
    ghat: Optional[np.ndarray] = None
    updated_prognostic: Dict[str, np.ndarray] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class MixingSchemeAdapter(ABC):
    """
    Abstract base class for mixing scheme adapters.

    Adapters wrap existing mixing implementations (KPPDriver, GGL90Core)
    to provide a common interface for the unified driver.
    """

    @property
    @abstractmethod
    def scheme_name(self) -> str:
        """Name of the mixing scheme (e.g., 'KPP', 'GGL90')."""
        pass

    @abstractmethod
    def initialize_prognostic_vars(
        self,
        grid: ColumnGrid,
        state: ColumnState
    ) -> Dict[str, np.ndarray]:
        """
        Initialize scheme-specific prognostic variables.

        Args:
            grid: Column grid specification
            state: Current state (for initialization that depends on T/S/U/V)

        Returns:
            Dictionary of prognostic variables to add to state.prognostic_vars
            - KPP: returns {} (diagnostic scheme)
            - GGL90: returns {'tke': initial_tke_array}
        """
        pass

    @abstractmethod
    def compute_mixing(
        self,
        state: ColumnState,
        grid: ColumnGrid,
        forcing: Dict[str, float],
        dt: float
    ) -> MixingOutput:
        """
        Compute mixing coefficients and update prognostic variables.

        Args:
            state: Current state (theta, salt, u_vel, v_vel, prognostic_vars)
            grid: Column grid specification
            forcing: Dictionary with surface forcing terms:
                     - tau_x, tau_y: Wind stress / rho [m²/s²]
                     - q_net, q_sw: Heat fluxes [W/m²]
                     - fw_flux: Freshwater flux [m/s]
                     - coriol: Coriolis parameter [1/s] (optional)
            dt: Time step [s]

        Returns:
            MixingOutput with diffusivities/viscosities and optional updates
        """
        pass


class KPPAdapter(MixingSchemeAdapter):
    """
    Adapter for KPP mixing scheme.

    Wraps the existing KPPDriver implementation to provide the common interface.
    KPP is a diagnostic scheme - it computes mixing coefficients directly from
    the current state without evolving prognostic variables.
    """

    def __init__(self, kpp_driver, background_visc: float = 1.0e-4,
                 background_diff: float = 1.0e-5):
        """
        Args:
            kpp_driver: Instance of KPPDriver from KPP
            background_visc: Background viscosity [m²/s]
            background_diff: Background diffusivity [m²/s]
        """
        self.kpp_driver = kpp_driver
        self.background_visc = background_visc
        self.background_diff = background_diff

    @property
    def scheme_name(self) -> str:
        return "KPP"

    def initialize_prognostic_vars(
        self,
        grid: ColumnGrid,
        state: ColumnState
    ) -> Dict[str, np.ndarray]:
        return {}

    def compute_mixing(
        self,
        state: ColumnState,
        grid: ColumnGrid,
        forcing: Dict[str, float],
        dt: float
    ) -> MixingOutput:
        coriol = forcing.get('coriol', 1.0e-4)

        kpp_output = self.kpp_driver.compute_mixing(
            theta=state.theta,
            salt=state.salt,
            u_vel=state.u_vel,
            v_vel=state.v_vel,
            depth=grid.depth,
            cell_thickness=grid.cell_thickness,
            tau_x=forcing['tau_x'],
            tau_y=forcing['tau_y'],
            q_net=forcing['q_net'],
            q_sw=forcing['q_sw'],
            fw_flux=forcing['fw_flux'],
            coriol=coriol,
            background_visc=self.background_visc,
            background_diff_s=self.background_diff,
            background_diff_t=self.background_diff,
        )

        diagnostics = {
            'hbl': kpp_output.hbl,
            'ustar': kpp_output.ustar,
            'bfsfc': kpp_output.bfsfc,
            'bulk_ri': kpp_output.bulk_ri,
            'shear_sq': kpp_output.shear_sq,
        }

        return MixingOutput(
            visc_az=kpp_output.visc_az,
            diff_kz_t=kpp_output.diff_kz_t,
            diff_kz_s=kpp_output.diff_kz_s,
            ghat=kpp_output.ghat,
            updated_prognostic={},
            diagnostics=diagnostics
        )


class GGL90Adapter(MixingSchemeAdapter):
    """
    Adapter for GGL90 mixing scheme.

    Wraps the existing GGL90Core implementation to provide the common interface.
    GGL90 is a prognostic scheme - it evolves turbulent kinetic energy (TKE)
    as a state variable.
    """

    def __init__(self, ggl90_driver, physical_params: Dict[str, float]):
        """
        Args:
            ggl90_driver: Instance of GGL90Driver from GGL90
            physical_params: Dict with 'gravity', 'rho_const', 'heat_capacity_cp',
                and optionally 'background_viscosity'/'background_diffusivity'
                (MITgcm's viscArNr(k)/diffKrNrS(k) background floor; default 0.0
                if not supplied).
        """
        self.ggl90_driver = ggl90_driver
        self.gravity = physical_params['gravity']
        self.rho_const = physical_params['rho_const']
        self.cp = physical_params['heat_capacity_cp']
        self.background_visc = physical_params.get('background_viscosity', 0.0)
        self.background_diff = physical_params.get('background_diffusivity', 0.0)

    @property
    def scheme_name(self) -> str:
        return "GGL90"

    def initialize_prognostic_vars(
        self,
        grid: ColumnGrid,
        state: ColumnState
    ) -> Dict[str, np.ndarray]:
        tke_min = self.ggl90_driver.params.tke_min
        tke_init = np.full(grid.nz, tke_min, dtype=np.float64)
        return {'tke': tke_init}

    def compute_mixing(
        self,
        state: ColumnState,
        grid: ColumnGrid,
        forcing: Dict[str, float],
        dt: float
    ) -> MixingOutput:
        # GGL90 needs theta, salt, and depth to compute potential density
        # gradients (N²) internally. Unlike the old implementation that
        # pre-computed in-situ density here, the driver now calls
        # compute_ggl90_buoyancy_frequency_squared which performs the
        # potential density gradient calculation matching MITgcm's sigmaR.

        tau_x = forcing['tau_x']
        tau_y = forcing['tau_y']
        u_star_sq = np.sqrt(tau_x**2 + tau_y**2)

        tke = state.prognostic_vars.get('tke')
        if tke is None:
            raise ValueError("GGL90 requires 'tke' in state.prognostic_vars")

        mask = np.ones(grid.nz, dtype=np.float64)

        ggl90_output = self.ggl90_driver.compute_mixing(
            tke=tke,
            u=state.u_vel,
            v=state.v_vel,
            theta=state.theta,
            salt=state.salt,
            depth=grid.depth,
            z=grid.z_positive_up,
            dz=grid.cell_thickness,
            dt=dt,
            mask=mask,
            u_star_sq=u_star_sq,
            gravity=self.gravity,
            rho_const=self.rho_const,
            background_visc=self.background_visc,
            background_diff=self.background_diff,
        )

        # GGL90 kappa_m/kappa_h are already on the MITgcm top-of-cell interface
        # convention (top face of cell k, surface face = 0) -- the same layout
        # the shared solver expects -- so they pass straight through with no
        # face-averaging or interpolation.
        visc_az = ggl90_output.kappa_m
        diff_kz = ggl90_output.kappa_h

        diagnostics = {
            'mixing_length': ggl90_output.mixing_length,
            'n_square': ggl90_output.n_square,
            'shear_square': ggl90_output.shear_square,
        }

        return MixingOutput(
            visc_az=visc_az,
            diff_kz_t=diff_kz,
            diff_kz_s=diff_kz,
            ghat=None,
            updated_prognostic={'tke': ggl90_output.tke_new},
            diagnostics=diagnostics
        )
