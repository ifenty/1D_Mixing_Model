#!/usr/bin/env python3
"""
Export one of the Python port's idealized mixing scenarios
(Vertical_Mixing_Models/simulations/scenarios/) to the standalone KPPMIX
driver's flat text input format (mitgcm_verification_mods/kpp_standalone_driver),
so the real Fortran KPPMIX can be run directly on inputs no MITgcm capture
has ever produced -- completing the three-way method's step (2) for these
scenarios (the same standalone driver already used for step (2) on real
MITgcm captures; see export_kpp_input_for_fortran.py, its counterpart for
that source).

Prerequisite: the scenario must already have been run via
Vertical_Mixing_Models/main/run_scenarios.py (producing
output/<scenario>/kpp_experiment.npz) -- this script only exports what that
run already computed (grid, per-timestep state, and KPPMIX's direct "I"-only
diagnostics: ustar/bo/bosol/shear_sq/buoy_freq_sq/dVsq/Ritop, all now part of
KPPOutput/KPPAdapter's diagnostics -- see kpp_core_driver.py/mixing_adapter.py).
Deliberately does not recompute or reimplement any of KPP's physics: the
whole point is to replay the exact numbers the Python port's own KPPDriver
already produced, not a fresh derivation of them.

Shortwave attenuation (swatt): all 6 scenarios use KPPParameters defaults
(shortwave_heating=False, select_penetrating_sw=0, confirmed directly --
run_scenarios.py never overrides them), so KPPMIX never consults swatt's
values regardless of what's exported; written as all-zero, matching
export_kpp_input_for_fortran.py's own fallback when swatt is unavailable.
"""

import sys
from pathlib import Path
from typing import Dict

import numpy as np
import yaml

PKG_DIR = Path(__file__).resolve().parent.parent.parent / "Vertical_Mixing_Models"
sys.path.insert(0, str(PKG_DIR))

from KPP.kpp_parameters import KPPParameters  # noqa: E402

SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
PHYSICAL_YAML = PKG_DIR / "configuration_yamls" / "physical_parameters.yaml"
OUTPUT_DIR = PKG_DIR / "output"

# Same KPP_PARAMS.h scalar list and order the standalone driver expects --
# see export_kpp_input_for_fortran.py's identical SCALAR_PARAMS (kept in
# sync manually; both target the same Fortran READ sequence in
# kpp_standalone_main.F).
SCALAR_PARAMS = [
    'Ricr', 'cekman', 'cmonob', 'concv', 'hbf',
    'epsilon', 'vonk', 'dB_dz',
    'Riinfty', 'BVSQcon', 'difm0', 'difs0', 'dift0',
    'difmcon', 'difscon', 'diftcon',
    'conc1', 'conam', 'concm', 'conc2', 'zetam',
    'conas', 'concs', 'conc3', 'zetas',
    'Rrho0', 'dsfmax',
    'epsln', 'phepsi', 'cstar', 'minKPPhbl',
    'zmin', 'zmax', 'umin', 'umax',
]
INT_PARAMS = ['num_v_smooth_Ri', 'selectPenetratingSW']
BOOL_PARAMS = ['KPPuseDoubleDiff', 'LimitHblStable', 'KPPuseSWfrac3D']

# KPPParameters uses snake_case names that don't all match the Fortran/
# MITgcm names above one-for-one; map the ones that differ.
_PARAM_NAME_MAP = {
    'num_v_smooth_Ri': 'num_v_smooth_ri',
    'selectPenetratingSW': 'select_penetrating_sw',
    'KPPuseDoubleDiff': 'use_doublediff',
    'LimitHblStable': 'limit_hbl_stable',
    'KPPuseSWfrac3D': 'use_sw_frac_3d',
}


def _get_param(params: KPPParameters, fortran_name: str, first_level_depth: float):
    if fortran_name == 'minKPPhbl':
        # KPPParameters.min_kpp_hbl=None does NOT mean "no floor" (an earlier,
        # incorrect assumption in this script -- confirmed wrong empirically:
        # 2 of 6 scenarios' standalone-driver hbl diverged from the Python
        # port's own hbl specifically at shallow, weakly-forced timesteps).
        # kpp_scheme_specific.py:233-236's real behavior: hbl = max(hbl,
        # min_kpp_hbl) if min_kpp_hbl is not None, ELSE hbl = max(hbl,
        # -zgrid[0]) -- the first grid level's depth is always the effective
        # floor. Re-verified after this fix: the 2 affected scenarios now
        # match the standalone driver to floating-point roundoff.
        return first_level_depth if params.min_kpp_hbl is None else params.min_kpp_hbl
    attr = _PARAM_NAME_MAP.get(fortran_name, fortran_name)
    return getattr(params, attr)


def _load_scenario_yaml(name: str, suffix: str) -> Dict:
    path = SCENARIO_DIR / f"scenario_{name}_{suffix}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def export(scenario_name: str, npz_path: Path, out_txt: Path) -> None:
    d = np.load(npz_path)

    nz = int(d['depth'].shape[0])
    n_out = int(d['visc_az'].shape[0])  # mixing-output timesteps (n_steps in the run)

    params = KPPParameters()  # run_scenarios.py's exact defaults (no kpp_yaml override)

    with open(PHYSICAL_YAML) as f:
        physical = yaml.safe_load(f)['physical_parameters']
    viscAzVal = physical['background_viscosity']
    diffKzVal = physical['background_diffusivity']

    forcing_yaml = _load_scenario_yaml(scenario_name, 'atmospheric_forcing')
    if forcing_yaml['metadata']['time_dependence'] != 'invariant':
        raise ValueError(
            f"scenario {scenario_name!r} has time-varying forcing "
            "(time_dependence != 'invariant') -- this export assumes the same "
            "forcing dict is used for every timestep, matching run_scenarios.py's "
            "current behavior; extend this script if that ever changes."
        )
    ic_yaml = _load_scenario_yaml(scenario_name, 'initial_conditions')
    coriol = float(ic_yaml['initial_conditions']['coriol'])

    lines = []
    lines.append(f"{n_out} {nz}")

    drF = d['cell_thickness']
    rC = d['depth']
    for k in range(nz):
        lines.append(f"{float(drF[k])!r} {float(rC[k])!r}")

    first_level_depth = -float(rC[0])  # rC is negative-down; see _get_param
    for name in SCALAR_PARAMS:
        lines.append(repr(float(_get_param(params, name, first_level_depth))))
    # viscAz/diffKzS/diffKzT are read separately by the driver, in this order,
    # right after the SCALAR_PARAMS loop -- see kpp_standalone_main.F. These
    # come from physical_parameters.yaml (KPPAdapter's background_visc/diff),
    # not KPPParameters, matching how run_scenarios.py wires them.
    lines.append(repr(float(viscAzVal)))
    lines.append(repr(float(diffKzVal)))
    lines.append(repr(float(diffKzVal)))
    for name in INT_PARAMS:
        lines.append(str(int(_get_param(params, name, first_level_depth))))
    for name in BOOL_PARAMS:
        lines.append(str(int(_get_param(params, name, first_level_depth))))

    ustar = d['ustar']
    bo = d['bo']
    bosol = d['bosol']
    shear_sq = d['shear_sq']
    dVsq = d['dVsq']
    buoy_freq_sq = d['buoy_freq_sq']
    Ritop = d['Ritop']

    for t in range(n_out):
        lines.append(f"{t}")
        lines.append(
            f"{float(ustar[t])!r} {float(bo[t])!r} "
            f"{float(bosol[t])!r} {coriol!r}"
        )
        for k in range(nz):
            lines.append(
                f"{float(shear_sq[t,k])!r} {float(dVsq[t,k])!r} "
                f"{float(buoy_freq_sq[t,k])!r} {float(Ritop[t,k])!r}"
            )
        for k in range(nz + 1):
            lines.append("0.0")  # swatt: unused, see module docstring

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_txt} ({n_out} timesteps, {nz} levels)")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python export_scenario_to_fortran.py <scenario_name> "
            "[npz_path] [out_txt]\n"
            "Example: python export_scenario_to_fortran.py hurricane_wind"
        )
        sys.exit(1)

    scenario_name = sys.argv[1]
    npz_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else (
        OUTPUT_DIR / scenario_name / "kpp_experiment.npz"
    )
    out_txt = Path(sys.argv[3]) if len(sys.argv) >= 4 else (
        OUTPUT_DIR / scenario_name / "kpp_standalone_input.txt"
    )

    if not npz_path.exists():
        print(f"Error: {npz_path} not found. Run main/run_scenarios.py first.")
        sys.exit(1)

    export(scenario_name, npz_path, out_txt)


if __name__ == '__main__':
    main()
