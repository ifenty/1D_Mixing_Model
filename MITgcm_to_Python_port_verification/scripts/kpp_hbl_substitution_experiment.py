#!/usr/bin/env python3
"""
1DMIX-056 decisive experiment: does substituting the real Fortran KPPMIX's own
`hbl` at each timestep, into the Python KPP port's boundary-layer shape
function, collapse `combined_storm`'s standalone-driver disagreement to
floating-point roundoff -- or does a residual survive?

MEASURED ANSWER: a material residual survives (see run_experiment() /
run_all_variants() and this issue's report update). hbl substitution alone
barely moves visc_az/diff_kz_s/diff_kz_t/ghat (n_gt_1pct changes by only a
few cells out of 600; max_abs is literally unchanged). Root-causing the
residual (the mismatching cells concentrate where sigma*hbl*bfsfc is most
negative, growing smoothly with depth/time rather than clustering at hbl)
pointed to `KPP.kpp_routines.py::wscale`'s own already-existing
`keep_mitgcm_bugs` validation-mode switch (kpp_routines.F:980 vs the
commented-out :990 fix; see `MITgcm_to_Python_port_verification/
KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md`, "Issue 2"): the
Python port's DEFAULT (`keep_mitgcm_bugs=False`) deliberately clamps the
wscale lookup-table extrapolation (the documented Sidorenko fix), while the
real, unmodified Fortran `KPPMIX` this standalone driver actually compiles
and runs has no such clamp -- it always takes the stock, unclamped
extrapolation. Instrumenting `wscale()` directly across all 6 scenarios
(Richard, round 2) shows the clamp-differentiating negative-`zdiff` branch is
technically *entered* by two of the other five as well -- `arctic_convection`
(25/2350 within-boundary-layer evaluation points) and `hurricane_wind`
(277/2424) -- but A/B-toggling `keep_mitgcm_bugs` produces zero measurable
change for any of the 5 calmer scenarios and only `combined_storm`'s
excursion is large enough for the clamp-vs-no-clamp difference to change the
measured result. Setting
`keep_mitgcm_bugs=True` -- with NO hbl override needed at all -- collapses
`hbl` itself to floating-point roundoff (same ~1e-14 magnitude as the other
5 scenarios) and drops visc_az/diff_kz_s/diff_kz_t/ghat's >1%-relative-error
cell count from 45-51% to ~0.7% (see run_all_variants()'s `keep_mitgcm_bugs`
key). The previously-reported small hbl disagreement (1DMIX-053, ~0.32 m)
was itself a downstream SYMPTOM of this same wscale difference (wscale feeds
diagnose_bl_depth's own Rib/bfsfc calculation), not an independent hbl
defect -- which is also why substituting hbl alone, while leaving
keep_mitgcm_bugs at its default, only partially helps: the same root
mechanism is still active inside diagnose_bl_depth's and compute_bl_mixing's
OWN wscale calls regardless of what hbl value is fed in.

A small residual remains even with keep_mitgcm_bugs=True: 4 of 600 visc_az
cells (0.7%), confined to the two deepest grid cells (k=48,49 of 50) at the
two timesteps where hbl has bottomed out to the full column depth
(kbl==nz) -- not further root-caused in this issue; see the report update
for the exact numbers. This script does not change any default -- it is a
read-only investigation tool; `keep_mitgcm_bugs` is passed explicitly by the
caller and was not touched here (it already existed, gated `False` by
default, before this issue).

Reuses, unmodified:
  - `compare_scenario_standalone.py::parse_standalone_output` (per-timestep
    Fortran `visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat`/`hbl` arrays)
  - `compare_scenario_ggl90_standalone.py::summarize` (the shared, scheme-
    agnostic per-field statistic function both the KPP and GGL90 standalone
    reports already use)

Does NOT reuse `compare_scenario_standalone.py::compare` itself, because that
function always compares the Python port's OWN unmodified `kpp_experiment.npz`
against Fortran -- there is no hook in it (nor should one be added, per this
issue's hard boundary against modifying that file) to inject a substituted
`hbl`. This script instead re-derives the mixing coefficients directly from
KPPMIX's own literal "I"-only per-timestep inputs already recorded in
`kpp_experiment.npz` (`shear_sq`, `buoy_freq_sq`=dbloc, `dVsq`, `Ritop`,
`ustar`, `bo`, `bosol`) via the actual production functions
(`KPP.kpp_routines.ri_iwmix`, `KPP.kpp_scheme_specific.diagnose_bl_depth`,
`::compute_bl_mixing`, `::enhance_at_interface`) -- the same orchestration
`KPPDriver.compute_mixing` performs in its Steps 4-9, just called directly so
the new `hbl_override` parameter (added to `diagnose_bl_depth`/
`compute_mixing` for this issue) can be threaded through per-timestep.

WHY NOT re-run KPPDriver.compute_mixing(theta=..., salt=..., ...) directly on
the npz's saved theta/salt/u_vel/v_vel: `combined_storm`'s own
time_integration.yaml has `output_frequency_steps=6` (`n_steps=72`, 12 mixing
outputs) -- mixing is computed and the column state diffused EVERY physics
step, but `DiagnosticsManager.save_snapshot` only records theta/salt/u_vel/
v_vel every 6th step. So the exact column state that produced saved mix_out
index j (an intermediate, un-saved state) is not recoverable from the
permanentized npz at all -- confirmed directly (re-running compute_mixing on
theta[j]/salt[j]/... gives up to ~43 m hbl disagreement with the recorded
hbl[j], a state/output granularity artifact, not a driver defect). What IS
saved, per output timestep, are KPPMIX's own literal call inputs (the "I"-
only diagnostics above) -- exactly the fields `export_scenario_to_fortran.py`
itself uses to build the Fortran driver's input file. Re-deriving from these
is therefore not just correct but the SAME correspondence the standalone-
driver comparison was already built on. Confirmed bit-identical (0.0 diff)
against the recorded visc_az/ghat/hbl with no override applied --see
`devel-loop/loop_state/1dmix056_scratch_orientation.py`.
"""

import json
import sys
from pathlib import Path

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_ROOT / "Vertical_Mixing_Models"))

from compare_scenario_standalone import parse_standalone_output  # noqa: E402
from compare_scenario_ggl90_standalone import summarize  # noqa: E402
from KPP.kpp_parameters import KPPParameters  # noqa: E402
from KPP.kpp_core_driver import KPPDriver  # noqa: E402
from KPP.kpp_routines import ri_iwmix  # noqa: E402
from KPP.kpp_scheme_specific import (  # noqa: E402
    diagnose_bl_depth, compute_bl_mixing, enhance_at_interface,
)

SCEN_DIR = (
    _ROOT / "MITgcm_to_Python_port_verification" / "KPP_port_validation"
    / "outputs_from_python_standalone" / "combined_storm"
)

BACKGROUND_VISC = 0.5e-4
BACKGROUND_DIFF_S = 1.0e-5
BACKGROUND_DIFF_T = 1.0e-5
CORIOL = 1.0e-4  # matches scenario_combined_storm_initial_conditions.yaml's own coriol=0.0001


def rederive_mixing(npz, params, wmt, wst, depth, cell_thickness, t, hbl_override=None):
    """Re-run KPPDriver.compute_mixing's Steps 4-9 from timestep t's recorded
    'I'-only diagnostics, optionally substituting hbl. Returns
    (hbl, visc_az, diff_kz_s, diff_kz_t, ghat), all on the same MITgcm
    top-of-cell/bottom-of-cell conventions KPPOutput itself uses.
    """
    nz = depth.shape[0]
    shsq = npz["shear_sq"][t]
    dbloc = npz["buoy_freq_sq"][t]
    dvsq = npz["dVsq"][t]
    Ritop = npz["Ritop"][t]
    ustar = float(npz["ustar"][t])
    bo = float(npz["bo"][t])
    bosol = float(npz["bosol"][t])

    bg_visc = np.full(nz, BACKGROUND_VISC)
    bg_diff_s = np.full(nz, BACKGROUND_DIFF_S)
    bg_diff_t = np.full(nz, BACKGROUND_DIFF_T)

    diffus_visc_int, diffus_s_int, diffus_t_int = ri_iwmix(
        shsq, dbloc, dbloc.copy(), bg_diff_s, bg_diff_t, params,
        zgrid=depth, visc_nr_bg=bg_visc,
    )
    hbl, bfsfc, stable, casea, kbl, bulk_ri = diagnose_bl_depth(
        dvsq, dbloc, Ritop, ustar, bo, bosol, CORIOL,
        depth, cell_thickness, wmt, wst, params, hbl_override=hbl_override,
    )
    blmc_visc, blmc_s, blmc_t, ghat, dkm1 = compute_bl_mixing(
        ustar, bfsfc, hbl, stable, casea,
        (diffus_visc_int, diffus_s_int, diffus_t_int),
        kbl, depth, cell_thickness, wmt, wst, params,
    )
    blmc_visc, blmc_s, blmc_t, ghat = enhance_at_interface(
        dkm1, hbl, kbl, (diffus_visc_int, diffus_s_int, diffus_t_int),
        casea, depth, cell_thickness, (blmc_visc, blmc_s, blmc_t), ghat,
    )

    visc_bot = np.zeros(nz)
    diff_s_bot = np.zeros(nz)
    diff_t_bot = np.zeros(nz)
    for k in range(nz):
        if k < kbl:
            visc_bot[k] = max(blmc_visc[k], BACKGROUND_VISC)
            diff_s_bot[k] = max(blmc_s[k], BACKGROUND_DIFF_S)
            diff_t_bot[k] = max(blmc_t[k], BACKGROUND_DIFF_T)
        else:
            visc_bot[k] = diffus_visc_int[k]
            diff_s_bot[k] = diffus_s_int[k]
            diff_t_bot[k] = diffus_t_int[k]
            ghat[k] = 0.0

    visc_az = np.zeros(nz)
    diff_kz_s = np.zeros(nz)
    diff_kz_t = np.zeros(nz)
    visc_az[1:] = visc_bot[:nz - 1]
    diff_kz_s[1:] = diff_s_bot[:nz - 1]
    diff_kz_t[1:] = diff_t_bot[:nz - 1]

    return hbl, visc_az, diff_kz_s, diff_kz_t, ghat


def run_variant(scenario_dir: Path, use_fortran_hbl: bool, keep_mitgcm_bugs: bool) -> dict:
    """Run one variant of the experiment and return a dict keyed by field
    name (visc_az/diff_kz_s/diff_kz_t/ghat/hbl) of the summarize() statistic
    dict, Fortran-vs-Python -- exactly what compare_scenario_standalone.py::
    compare already reports, but recomputed via rederive_mixing so `hbl` and
    `KPPParameters.keep_mitgcm_bugs` (kpp_routines.py's own existing
    wscale-lookup-table-extrapolation validation-mode switch) can be
    independently varied.

    use_fortran_hbl : if True, substitute each timestep's Fortran standalone-
        driver hbl for the Python-diagnosed one (the issue's decisive
        experiment). If False, use the Python port's own diagnosed hbl
        (the ordinary, unmodified code path).
    keep_mitgcm_bugs : passed straight through to KPPParameters -- True
        reproduces the real stock (unclamped) MITgcm wscale lookup-table
        extrapolation the actual standalone Fortran KPPMIX driver runs
        unconditionally (no equivalent flag exists on the Fortran side);
        False (default) is the Python port's own "bug-fixed" clamped
        default.
    """
    npz = np.load(scenario_dir / "kpp_experiment.npz")
    nz = int(npz["depth"].shape[0])
    depth = npz["depth"]
    cell_thickness = npz["cell_thickness"]
    n_out = int(npz["hbl"].shape[0])

    fortran = parse_standalone_output(scenario_dir / "kpp_standalone_output.txt", nz)

    params = KPPParameters(keep_mitgcm_bugs=keep_mitgcm_bugs)
    driver = KPPDriver(params)
    wmt, wst = driver.wmt, driver.wst

    out = {name: np.zeros((n_out, nz)) for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat")}
    out_hbl = np.zeros(n_out)

    for t in range(n_out):
        override = float(fortran["hbl"][t]) if use_fortran_hbl else None
        hbl, va, ds, dt, gh = rederive_mixing(
            npz, params, wmt, wst, depth, cell_thickness, t, hbl_override=override,
        )
        out_hbl[t] = hbl
        out["visc_az"][t] = va
        out["diff_kz_s"][t] = ds
        out["diff_kz_t"][t] = dt
        out["ghat"][t] = gh

    results = {}
    for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat"):
        results[name] = summarize(name, fortran[name], out[name])
    results["hbl"] = summarize("hbl", fortran["hbl"], out_hbl)
    return results


def run_experiment(scenario_dir: Path = SCEN_DIR) -> dict:
    """Run the issue's decisive experiment and return
    {'baseline': {...}, 'substituted': {...}}: (a) the Python port's own
    unmodified default (keep_mitgcm_bugs=False, Python's own diagnosed hbl)
    and (b) the same default config with each timestep's Python hbl replaced
    by the Fortran standalone driver's own hbl at that timestep
    (substituted) -- isolating whether hbl alone explains the disagreement.
    See run_all_variants() for the follow-on root-cause variant
    (keep_mitgcm_bugs=True) that this experiment's residual led to.
    """
    return {
        "baseline": run_variant(scenario_dir, use_fortran_hbl=False, keep_mitgcm_bugs=False),
        "substituted": run_variant(scenario_dir, use_fortran_hbl=True, keep_mitgcm_bugs=False),
    }


def run_all_variants(scenario_dir: Path = SCEN_DIR) -> dict:
    """All three variants examined by this issue's investigation:
      - baseline: default config, Python's own diagnosed hbl (the currently
        reported combined_storm disagreement).
      - hbl_substituted: default config, Fortran's own hbl substituted (the
        issue's decisive experiment -- tests whether hbl alone explains it).
      - keep_mitgcm_bugs: keep_mitgcm_bugs=True, Python's own diagnosed hbl
        (the root-cause finding -- tests whether matching the real stock
        MITgcm wscale lookup-table behaviour, independent of any hbl
        substitution, explains it instead).
    """
    return {
        "baseline": run_variant(scenario_dir, use_fortran_hbl=False, keep_mitgcm_bugs=False),
        "hbl_substituted": run_variant(scenario_dir, use_fortran_hbl=True, keep_mitgcm_bugs=False),
        "keep_mitgcm_bugs": run_variant(scenario_dir, use_fortran_hbl=False, keep_mitgcm_bugs=True),
    }


def _fmt(r: dict) -> str:
    return (f"max_abs={r['max_abs']:.3e} median_abs={r['median_abs']:.3e} "
            f"p95_abs={r['p95_abs']:.3e} max_rel={r['max_rel']:.3e} "
            f"n_gt_1pct={r['n_gt_1pct']}/{r['n_total']}")


def main():
    results = run_all_variants()
    print("combined_storm KPP investigation (1DMIX-056):\n")
    for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat", "hbl"):
        print(f"  {name}:")
        print(f"    baseline          (default config, Python's own hbl):     {_fmt(results['baseline'][name])}")
        print(f"    hbl_substituted   (default config, Fortran's hbl):        {_fmt(results['hbl_substituted'][name])}")
        print(f"    keep_mitgcm_bugs  (keep_mitgcm_bugs=True, Python's hbl):  {_fmt(results['keep_mitgcm_bugs'][name])}")
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
