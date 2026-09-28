#!/usr/bin/env python3
"""
Export one of the Python port's idealized mixing scenarios
(Vertical_Mixing_Models/simulations/scenarios/) to the standalone
GGL90_CALC driver's flat text input format
(mitgcm_verification_mods/ggl90_standalone_driver), so the real Fortran
GGL90_CALC can be run directly on inputs no MITgcm capture has ever
produced -- completing 1DMIX-024's scenario-extension scope (mirroring
export_scenario_to_fortran.py, KPP's counterpart for 1DMIX-023).

**Decisive premise verified before writing this script (contradicts a
literal reading of the original brief -- reported, not papered over)**:
unlike KPP (a purely diagnostic scheme, whose every per-call input is
recorded at the SAME output row as its own outputs), GGL90 is prognostic
and ALSO needs the actual u/v profile from the timestep immediately
BEFORE the one that produced a given output row. All 6 scenarios' already
-generated `ggl90_experiment.npz` use `output_frequency_steps` > 1 (6 or
100, see simulations/scenarios/scenario_*_time_integration.yaml) -- i.e.
they are *subsampled*: the state saved at output row t is the state AFTER
`output_frequency_steps` internal timesteps from row t-1, but the mixing
fields saved at row t (visc_az, diff_kz, mixing_length, n_square,
tke_after) were computed from the state ONE INTERNAL STEP EARLIER than
that, which is *not* one of the saved rows whenever `output_frequency_
steps > 1`. This was confirmed empirically (not just by reading the loop
in unified_driver.py): a throwaway two-run comparison (coarse run at the
scenario's own output_frequency_steps vs. a dense run at frequency=1)
showed the coarse-run outputs match the dense run's row at internal index
(t*F - 1) exactly (0.0 diff), which is NOT any row present in the coarse
file itself for F>1.

Resolution: this script reruns the scenario itself at
output_frequency_steps=1 (dt_seconds/n_steps unchanged -- same exact
physics, only the *sampling* of diagnostics changes) via the same
UnifiedColumnDriver/ConfigManager/GGL90Adapter machinery run_scenarios.py
uses, and exports FROM THAT dense trajectory. The existing coarse
`ggl90_experiment.npz` files (used elsewhere, e.g. plotting) are left
completely untouched; this script's dense run is saved separately
(default `output/<scenario>/ggl90_experiment_dense.npz`) purely as
inspectable evidence.

With the dense (frequency=1) trajectory, row i (0-indexed, i=0..n_steps-1)
of visc_az/diff_kz_s/diff_kz_t/mixing_length/n_square/shear_square pairs
EXACTLY with INPUT state theta[i]/salt[i]/u_vel[i]/v_vel[i]/tke[i] (the
`tke` prognostic-var array, length n_steps+1, unconditionally saved every
step) and OUTPUT tke_after = tke[i+1] -- confirmed by the same throwaway
script (feeding theta[i]/salt[i]/u_vel[i]/v_vel[i]/tke[i] through a fresh
GGL90Adapter.compute_mixing call reproduces visc_az[i] and tke[i+1] to
0.0 abs diff, i.e. exact self-consistency of the index mapping, for every
i checked).

sigmaR (GGL90_CALC's one explicit array argument) is derived by EXACTLY
inverting this scenario's own n_square[i,:] (NOT via main/eos.py --
deliberately, per the issue brief, to sidestep any EOS confound):
    sigmaR = -n_square * rho_const / gravity
matching ggl90_calc.F:347-348 (Nsquare = gravity*gravitySign*recip_
rhoConst*sigmaR*coordFac, gravitySign=-1 for z-coordinates per
model/src/ini_parms.F, coordFac=1 for usingPCoords=.FALSE.) -- confirmed
by reading ggl90_calc.F directly, not assumed from the brief.

tau_x/tau_y (needed for the surface TKE boundary condition's uStarSquare)
are read directly from the scenario's own atmospheric_forcing.yaml
(constant across the whole run -- confirmed `time_dependence: invariant`
for all 6 scenarios' GGL90-relevant forcing, same file KPP's own export
script already checks). This reproduces GGL90Adapter.compute_mixing's own
u_star_sq = sqrt(tau_x**2+tau_y**2) EXACTLY, since GGL90_CALC's two
calcMeanVertShear branches both reduce (for a single column replicated
into every halo position) to uStarSquare_pre_sqrt = tauX**2+tauY**2, and
the driver's own subsequent SQRT(...)*recip_coordFac (recip_coordFac=1)
gives exactly sqrt(tauX**2+tauY**2) as the value used at every
GGL90m2*uStarSquare term downstream -- i.e. no artificial component
"splitting" is needed at all when the real tau_x/tau_y are available
directly (unlike a hypothetical case with only a combined scalar u_star_sq
on hand).
"""

import sys
from pathlib import Path
from typing import Dict

import numpy as np
import yaml

PKG_DIR = Path(__file__).resolve().parent.parent.parent / "Vertical_Mixing_Models"
sys.path.insert(0, str(PKG_DIR))

import os  # noqa: E402
os.environ.setdefault("KPP_PHYSICAL_PARAMETERS_YAML",
                       str(PKG_DIR / "configuration_yamls" / "physical_parameters.yaml"))

from main import UnifiedColumnDriver, ConfigManager, GGL90Adapter  # noqa: E402
from GGL90.ggl90_core_driver import GGL90Driver  # noqa: E402
from GGL90.ggl90_parameters import GGL90Parameters  # noqa: E402

SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
PHYSICAL_YAML = PKG_DIR / "configuration_yamls" / "physical_parameters.yaml"
OUTPUT_DIR = PKG_DIR / "output"

# Fortran driver's READ order for GGL90.h/PARAMS.h scalars -- matches
# export_vermix_capture_to_ggl90_driver.py's identical FLOAT_PARAMS/
# INT_PARAMS/BOOL_PARAMS (same driver, same ggl90_standalone_main.F READ
# sequence; kept in sync manually).
FLOAT_PARAMS = [
    'GGL90ck', 'GGL90ceps', 'GGL90alpha', 'GGL90m2',
    'GGL90TKEmin', 'GGL90TKEsurfMin', 'GGL90TKEbottom',
    'GGL90mixingLengthMin', 'GGL90viscMax', 'GGL90diffMax',
    'gravity', 'rhoConst', 'viscAz', 'diffKzS', 'deltaT',
]
INT_PARAMS = ['mxlMaxFlag']
BOOL_PARAMS = ['GGL90_dirichlet', 'calcMeanVertShear']

# GGL90Parameters attribute names that don't match the Fortran names above
# one-for-one.
_PARAM_NAME_MAP = {
    'GGL90ck': 'ck',
    'GGL90ceps': 'ceps',
    'GGL90alpha': 'alpha',
    'GGL90m2': 'm2',
    'GGL90TKEmin': 'tke_min',
    'GGL90TKEsurfMin': 'tke_surf_min',
    'GGL90TKEbottom': 'tke_bottom',
    'GGL90mixingLengthMin': 'mixing_length_min',
    'GGL90viscMax': 'visc_max',
    'GGL90diffMax': 'diff_max',
    'mxlMaxFlag': 'mxl_max_flag',
    'GGL90_dirichlet': 'use_dirichlet',
    'calcMeanVertShear': 'calc_mean_vert_shear',
}


def _load_scenario_yaml(name: str, suffix: str) -> Dict:
    path = SCENARIO_DIR / f"scenario_{name}_{suffix}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def _config_manager_for(name: str) -> ConfigManager:
    return ConfigManager(
        config_dir=SCENARIO_DIR,
        prefix=f"scenario_{name}_",
        physical_params_path=PHYSICAL_YAML,
    )


def run_dense(scenario_name: str, dense_npz_path: Path) -> tuple[dict, "ColumnGrid", float]:
    """Rerun the scenario at output_frequency_steps=1 (dt_seconds/n_steps
    unchanged -- same physics, denser sampling) and save the resulting
    per-internal-step trajectory. Returns (diagnostics_dict, grid, dt).
    """
    config_mgr = _config_manager_for(scenario_name)
    physical = config_mgr.load_physical_parameters()

    orig_time = config_mgr.load_time_integration()
    dt = float(orig_time['dt_seconds'])

    def _dense_time_integration():
        d = dict(orig_time)
        d['output_frequency_steps'] = 1
        return d
    # Monkeypatch this ConfigManager instance only -- leaves the on-disk
    # scenario_*_time_integration.yaml (and hence the existing coarse
    # ggl90_experiment.npz) completely untouched.
    config_mgr.load_time_integration = _dense_time_integration

    params = GGL90Parameters.from_yaml(None)  # run_scenarios.py's exact
    # defaults for these 6 scenarios (no --ggl90-yaml override was used to
    # generate the existing coarse npz's -- confirmed: no per-scenario
    # GGL90 yaml override file exists under simulations/scenarios/).
    adapter = GGL90Adapter(GGL90Driver(params), physical)
    driver = UnifiedColumnDriver(adapter, config_mgr, physical)

    dense_npz_path.parent.mkdir(parents=True, exist_ok=True)
    results = driver.run_experiment(output_path=dense_npz_path)
    return results['diagnostics'], driver.grid, dt, params, physical


def export(scenario_name: str, dense_npz_path: Path, out_txt: Path) -> None:
    diag, grid, dt, params, physical = run_dense(scenario_name, dense_npz_path)

    nz = grid.nz
    n_out = int(diag['visc_az'].shape[0])  # == n_steps (one row per internal step)
    theta = diag['theta']
    salt = diag['salt']
    u_vel = diag['u_vel']
    v_vel = diag['v_vel']
    tke = diag['tke']
    n_square = diag['n_square']

    assert theta.shape[0] == n_out + 1, (
        f"expected theta to have n_out+1={n_out + 1} rows (dense, unconditional "
        f"save including the initial condition), got {theta.shape[0]}"
    )
    assert tke.shape[0] == n_out + 1, (
        f"expected tke to have n_out+1={n_out + 1} rows, got {tke.shape[0]}"
    )

    forcing_yaml = _load_scenario_yaml(scenario_name, 'atmospheric_forcing')
    if forcing_yaml['metadata']['time_dependence'] != 'invariant':
        raise ValueError(
            f"scenario {scenario_name!r} has time-varying forcing "
            "(time_dependence != 'invariant') -- this export assumes the same "
            "tau_x/tau_y apply at every timestep, matching how unified_driver.py "
            "loads the forcing dict once and reuses it for the whole run; extend "
            "this script if that ever changes."
        )
    tau_x = float(forcing_yaml['atmospheric_forcing']['tau_x'])
    tau_y = float(forcing_yaml['atmospheric_forcing']['tau_y'])
    u_star_sq = float(np.sqrt(tau_x**2 + tau_y**2))  # for the record only;
    # unused by the Fortran driver, which recomputes uStarSquare itself from
    # surfaceForcingU/V=tauX,tauY (see module docstring).

    gravity = float(physical['gravity'])
    rho_const = float(physical['rho_const'])

    lines = []
    lines.append(f"{n_out} {nz}")

    drF = grid.cell_thickness
    rF = grid.interfaces  # shape (nz+1,); rF[0]=0=surface, matches Fortran rF(1..Nr+1)
    rC = grid.depth
    for k in range(nz):
        lines.append(f"{float(drF[k])!r} {float(rF[k])!r} {float(rC[k])!r}")

    def _param(fortran_name):
        attr = _PARAM_NAME_MAP.get(fortran_name)
        if attr is not None:
            return getattr(params, attr)
        if fortran_name == 'gravity':
            return gravity
        if fortran_name == 'rhoConst':
            return rho_const
        if fortran_name == 'viscAz':
            return physical['background_viscosity']
        if fortran_name == 'diffKzS':
            return physical['background_diffusivity']
        if fortran_name == 'deltaT':
            return dt
        raise KeyError(fortran_name)

    for name in FLOAT_PARAMS:
        lines.append(repr(float(_param(name))))
    for name in INT_PARAMS:
        lines.append(str(int(_param(name))))
    for name in BOOL_PARAMS:
        lines.append(str(int(bool(_param(name)))))

    for i in range(n_out):
        lines.append(f"{i}")
        lines.append(f"{tau_x!r} {tau_y!r} {u_star_sq!r}")
        for k in range(nz):
            lines.append(
                f"{float(theta[i, k])!r} {float(salt[i, k])!r} "
                f"{float(u_vel[i, k])!r} {float(v_vel[i, k])!r}"
            )
        for k in range(nz):
            lines.append(f"{float(tke[i, k])!r}")  # tke BEFORE this step (input)
        for k in range(nz):
            sigma_r_k = -float(n_square[i, k]) * rho_const / gravity
            lines.append(repr(sigma_r_k))

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_txt} ({n_out} timesteps, {nz} levels)")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python export_scenario_to_ggl90_driver.py <scenario_name> "
            "[dense_npz_path] [out_txt]\n"
            "Example: python export_scenario_to_ggl90_driver.py hurricane_wind"
        )
        sys.exit(1)

    scenario_name = sys.argv[1]
    dense_npz_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else (
        OUTPUT_DIR / scenario_name / "ggl90_experiment_dense.npz"
    )
    out_txt = Path(sys.argv[3]) if len(sys.argv) >= 4 else (
        OUTPUT_DIR / scenario_name / "ggl90_standalone_input.txt"
    )

    export(scenario_name, dense_npz_path, out_txt)


if __name__ == '__main__':
    main()
