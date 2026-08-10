"""
Unified 1D ocean column model driver.

Orchestrates time-stepping for 1D column experiments with different mixing schemes.
Follows MITgcm pattern: compute mixing → apply implicit diffusion → update state.
"""

from pathlib import Path
from typing import Dict, Optional
import numpy as np

from .column_grid import ColumnGrid
from .column_state import ColumnState
from .mixing_adapter import MixingSchemeAdapter, MixingOutput
from .config_manager import ConfigManager
from .shared_column_solver import solve_diffusion_implicit
from .eos import compute_static_instability_mask


class UnifiedColumnDriver:
    """
    Main driver for 1D column model time-stepping.

    Manages:
    - Grid and state initialization from configs
    - Time-stepping loop
    - Application of vertical diffusion
    - Diagnostics collection

    Args:
        mixing_adapter: Mixing scheme adapter (KPPAdapter or GGL90Adapter)
        config_manager: Configuration manager
        physical_params: Physical constants dict
    """

    def __init__(
        self,
        mixing_adapter: MixingSchemeAdapter,
        config_manager: ConfigManager,
        physical_params: Dict[str, float]
    ):
        self.mixing = mixing_adapter
        self.config = config_manager
        self.gravity = physical_params['gravity']
        self.rho_const = physical_params['rho_const']
        self.cp = physical_params['heat_capacity_cp']
        self.ivdc_kappa = physical_params.get('ivdc_kappa', 0.0)

        self.grid: Optional[ColumnGrid] = None
        self.state: Optional[ColumnState] = None

    def initialize_from_config(self) -> tuple[ColumnGrid, ColumnState, Dict]:
        """
        Initialize grid, state, and forcing from configuration files.

        Returns:
            Tuple of (grid, initial_state, forcing_dict)
        """
        ic = self.config.load_initial_conditions()
        forcing = self.config.load_atmospheric_forcing()

        grid = ColumnGrid.from_drF(np.array(ic['drF']))

        state = ColumnState(
            theta=np.array(ic['theta']),
            salt=np.array(ic['salt']),
            u_vel=np.array(ic['u_vel']),
            v_vel=np.array(ic['v_vel'])
        )
        state.validate(grid.nz)

        prognostic_vars = self.mixing.initialize_prognostic_vars(grid, state)
        state.prognostic_vars.update(prognostic_vars)

        forcing['coriol'] = ic.get('coriol', 1.0e-4)

        return grid, state, forcing

    def _compute_kinematic_surface_fluxes(
        self,
        forcing: Dict[str, float],
        surface_salt: float
    ) -> Dict[str, float]:
        """
        Convert forcing to kinematic surface fluxes.

        Args:
            forcing: Raw forcing dict (q_net, q_sw, fw_flux, tau_x, tau_y)
            surface_salt: Surface salinity for salt flux computation

        Returns:
            Dict with kinematic fluxes: heat_flux, salt_flux, tau_x, tau_y
        """
        heat_flux = forcing['q_net'] / (self.rho_const * self.cp)

        salt_flux = -forcing['fw_flux'] * surface_salt

        return {
            'heat_flux': heat_flux,
            'salt_flux': salt_flux,
            'tau_x': forcing['tau_x'],
            'tau_y': forcing['tau_y']
        }

    def _apply_convective_adjustment(
        self,
        state: ColumnState,
        grid: ColumnGrid,
        mix_out: MixingOutput,
    ):
        """
        Add MITgcm's `ivdc_kappa` convective-adjustment diffusivity on top of
        whatever the active mixing scheme (KPP or GGL90) already computed,
        wherever the column is statically unstable. Scheme-independent, and
        applied to tracer diffusivity only (not viscosity), matching
        MITgcm's calc_3d_diffusivity.F. Modifies mix_out in place. No-op when
        ivdc_kappa is 0 (MITgcm's own default / off), matching
        `calcConvect = ivdc_kappa .NE. 0.` in do_oceanic_phys.F.
        """
        if self.ivdc_kappa == 0.0:
            return

        unstable = compute_static_instability_mask(
            state.theta, state.salt, grid.depth, self.rho_const
        )
        mix_out.diff_kz_t = mix_out.diff_kz_t + unstable * self.ivdc_kappa
        mix_out.diff_kz_s = mix_out.diff_kz_s + unstable * self.ivdc_kappa

    def _apply_vertical_diffusion(
        self,
        state: ColumnState,
        grid: ColumnGrid,
        mix_out: MixingOutput,
        kinematic_fluxes: Dict[str, float],
        dt: float
    ):
        """
        Apply implicit vertical diffusion to all prognostic variables.

        Updates state in place.

        Args:
            state: Current state (modified in place)
            grid: Grid specification
            mix_out: Mixing coefficients from mixing scheme
            kinematic_fluxes: Surface fluxes (heat, salt, momentum)
            dt: Time step [s]
        """
        state.theta = solve_diffusion_implicit(
            c_old=state.theta,
            k_interface=mix_out.diff_kz_t,
            depth=grid.depth,
            thickness=grid.cell_thickness,
            dt=dt,
            surface_flux=kinematic_fluxes['heat_flux'],
            ghat=mix_out.ghat
        )

        state.salt = solve_diffusion_implicit(
            c_old=state.salt,
            k_interface=mix_out.diff_kz_s,
            depth=grid.depth,
            thickness=grid.cell_thickness,
            dt=dt,
            surface_flux=kinematic_fluxes['salt_flux'],
            ghat=mix_out.ghat
        )

        state.u_vel = solve_diffusion_implicit(
            c_old=state.u_vel,
            k_interface=mix_out.visc_az,
            depth=grid.depth,
            thickness=grid.cell_thickness,
            dt=dt,
            surface_flux=kinematic_fluxes['tau_x']
        )

        state.v_vel = solve_diffusion_implicit(
            c_old=state.v_vel,
            k_interface=mix_out.visc_az,
            depth=grid.depth,
            thickness=grid.cell_thickness,
            dt=dt,
            surface_flux=kinematic_fluxes['tau_y']
        )

        if mix_out.updated_prognostic:
            state.prognostic_vars.update(mix_out.updated_prognostic)

    def run_experiment(
        self,
        output_path: Optional[Path] = None,
        grid: Optional[ColumnGrid] = None,
        state: Optional[ColumnState] = None,
        forcing: Optional[Dict] = None
    ) -> Dict:
        """
        Run complete time-stepping experiment.

        Args:
            output_path: Path for saving diagnostics NPZ file (optional)
            grid: Grid specification (uses config if None)
            state: Initial state (uses config if None)
            forcing: Forcing dict (uses config if None)

        Returns:
            Dictionary with final state and diagnostics
        """
        if grid is None or state is None or forcing is None:
            grid, state, forcing = self.initialize_from_config()

        self.grid = grid
        self.state = state

        time_config = self.config.load_time_integration()
        dt = float(time_config['dt_seconds'])
        n_steps = int(time_config['n_steps'])
        output_freq = int(time_config['output_frequency_steps'])

        from .diagnostics import DiagnosticsManager
        diag = DiagnosticsManager(
            grid,
            self.mixing.scheme_name,
            rho_const=self.rho_const,
        )

        print(f"Running {self.mixing.scheme_name} experiment:")
        print(f"  Grid: {grid}")
        print(f"  Time steps: {n_steps}, dt={dt}s")
        print(f"  Output frequency: every {output_freq} steps")
        print(f"  Total time: {n_steps * dt / 86400:.1f} days")
        if self.ivdc_kappa != 0.0:
            print(f"  Convective adjustment (ivdc_kappa): {self.ivdc_kappa} m²/s")

        for step in range(n_steps + 1):
            if step % output_freq == 0:
                diag.save_snapshot(step * dt, state, mix_out if step > 0 else None)

                if step % (10 * output_freq) == 0:
                    print(f"  Step {step}/{n_steps}, "
                          f"SST={state.theta[0]:.2f}°C, "
                          f"SSS={state.salt[0]:.2f}psu")

            if step < n_steps:
                mix_out = self.mixing.compute_mixing(state, grid, forcing, dt)
                self._apply_convective_adjustment(state, grid, mix_out)

                kinematic_fluxes = self._compute_kinematic_surface_fluxes(
                    forcing, state.salt[0]
                )

                self._apply_vertical_diffusion(
                    state, grid, mix_out, kinematic_fluxes, dt
                )

        results = {
            'final_state': state,
            'diagnostics': diag.get_diagnostics()
        }

        if output_path:
            diag.save_to_file(output_path)
            print(f"\nDiagnostics saved to: {output_path}")

        return results
