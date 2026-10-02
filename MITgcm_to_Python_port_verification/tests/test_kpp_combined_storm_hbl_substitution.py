"""
Regression witness for 1DMIX-056's combined_storm KPP investigation.

Locks in the MEASURED conclusion (not an aspirational one): substituting the
real Fortran KPPMIX's own `hbl` per timestep into the Python KPP port does
NOT collapse `combined_storm`'s standalone-driver disagreement -- a material
residual survives, proving hbl alone does not explain it. The actual root
cause is `KPP.kpp_routines.py::wscale`'s pre-existing `keep_mitgcm_bugs`
validation-mode switch (kpp_routines.F:980 vs the commented-out :990 fix):
setting it True (no hbl override needed) collapses the disagreement to
floating-point-roundoff `hbl`. Until 1DMIX-075 a small residual remained in
visc_az/diff_kz_s/diff_kz_t/ghat (4 / 2 / 2 / 3 of 600 cells, max 2.7e-3 /
2.7e-3 / 2.7e-3 / 0.858) at the timesteps where the boundary layer has deepened
to the full column; 1DMIX-075 found its cause (the port's 'none found' `kbl`
was `nz` where MITgcm's is `Nr`, kpp_routines.F:807,818-824, with its
consequences for `blmix`/`enhance`/`ghat(Nr)`) and the residual is now exactly
0 (max_abs 0.0, every field).

See `MITgcm_to_Python_port_verification/scripts/
kpp_hbl_substitution_experiment.py` for the experiment itself (reused here,
not reimplemented) and `KPP_port_validation/reports/
kpp_scenario_standalone_summary.md`'s `combined_storm` section for the
narrative writeup. Tolerances below are the actually-measured values from
that experiment (with headroom), not aspirational ones -- if this ever
starts failing, either `KPP/kpp_scheme_specific.py::diagnose_bl_depth`'s new
`hbl_override` plumbing, `KPP/kpp_routines.py::wscale`'s `keep_mitgcm_bugs`
gating, or the permanentized `combined_storm` standalone-driver data itself
has changed -- worth investigating either way, not silently loosening this
test.
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from kpp_hbl_substitution_experiment import (  # noqa: E402
    SCEN_DIR, run_all_variants,
)

NPZ = SCEN_DIR / "kpp_experiment.npz"
FORTRAN_TXT = SCEN_DIR / "kpp_standalone_output.txt"


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"Required permanentized standalone-driver data not found: {path}")


@pytest.fixture(scope="module")
def variants():
    _require(NPZ)
    _require(FORTRAN_TXT)
    return run_all_variants(SCEN_DIR)


def test_baseline_matches_the_established_disagreement(variants):
    """Sanity: the unmodified default-config comparison still reproduces the
    magnitude kpp_scenario_standalone_summary.md reports (45-51% of cells
    >1% relative error) -- if this drifts, the permanentized data or the
    default KPP code path has changed and the rest of this test's
    conclusions need re-checking, not just this one number.
    """
    b = variants["baseline"]
    assert b["visc_az"]["n_gt_1pct"] >= 200, (
        f"baseline visc_az n_gt_1pct={b['visc_az']['n_gt_1pct']}/600 is far below the "
        "established ~270/600 -- the combined_storm baseline disagreement this "
        "investigation was built on may have changed"
    )
    assert b["hbl"]["max_abs"] > 0.1, (
        f"baseline hbl max_abs={b['hbl']['max_abs']:.3e} m is far below the established "
        "~0.32 m -- re-check before trusting the variants below"
    )


def test_hbl_substitution_alone_leaves_a_material_residual(variants):
    """The issue's decisive experiment: hbl alone does NOT explain the
    disagreement. n_gt_1pct barely moves (270->261/600 measured) and max_abs
    is unchanged to displayed precision -- assert generously (>=200/600,
    i.e. still >30% of cells) so this only fails if the residual actually
    collapses, not on ordinary noise.
    """
    s = variants["hbl_substituted"]
    assert s["visc_az"]["n_gt_1pct"] >= 200, (
        f"visc_az n_gt_1pct={s['visc_az']['n_gt_1pct']}/600 after hbl substitution is much "
        "lower than measured (~261/600) -- hbl substitution may now be explaining far more "
        "of the disagreement than this investigation found; re-derive the conclusion"
    )
    assert s["hbl"]["max_abs"] < 1e-6, (
        "hbl substitution should force hbl itself to roundoff by construction"
    )


def test_keep_mitgcm_bugs_explains_the_residual(variants):
    """The root-cause finding: keep_mitgcm_bugs=True (matching the real,
    unmodified Fortran KPPMIX's own wscale lookup-table extrapolation, no
    hbl override needed at all) collapses hbl to floating-point roundoff and
    drops visc_az/diff_kz_s/diff_kz_t/ghat's >1%-cell count from ~270-308/600
    to ZERO since 1DMIX-075 (it was 4/2/2/3 of 600 before: those cells were
    the full-column 'none found' `kbl`, fixed there). Measured 2026-10-02:
    hbl max_abs 0.0 m (was 2.8e-14), every mixing field max_abs 0.0 (bit-exact against
    the standalone Fortran KPPMIX). Tolerances: the file's existing 1e-9
    convention for hbl, applied to the four fields too (before: n_gt_1pct <= 20,
    max_abs < 0.01)."""
    k = variants["keep_mitgcm_bugs"]
    assert k["hbl"]["max_abs"] < 1e-9, (
        f"hbl max_abs={k['hbl']['max_abs']:.3e} m with keep_mitgcm_bugs=True is far above "
        "floating-point roundoff -- the wscale root-cause finding may no longer hold"
    )
    for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat"):
        assert k[name]["n_gt_1pct"] == 0, (
            f"{name} n_gt_1pct={k[name]['n_gt_1pct']}/600 with keep_mitgcm_bugs=True: the combined_storm "
            "standalone-Fortran disagreement was 0 after 1DMIX-075 (full-column kbl)"
        )
        assert k[name]["max_abs"] < 1e-9, (
            f"{name} max_abs={k[name]['max_abs']:.3e} with keep_mitgcm_bugs=True exceeds the "
            "measured bit-exact agreement (0.0) beyond the 1e-9 convention"
        )
