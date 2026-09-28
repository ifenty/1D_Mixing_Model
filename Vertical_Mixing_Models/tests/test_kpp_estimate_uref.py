"""
Unit tests for KPPDriver._estimate_reference_velocity() -- regression coverage
for 1DMIX-032.

1DMIX-032 root cause (verified against
/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_forcing_surf.F, the real
MITgcm source this project ports): `vermix`'s KPP_OPTIONS.h defines
KPP_ESTIMATE_UREF (confirmed absent -- explicitly `#undef` -- in every other
tested KPP experiment's resolved headers), which switches MITgcm's `dVsq`
("velocity shear squared relative to surface") from the simple
`(u[0]-u[k])**2+(v[0]-v[k])**2` formula to a resolution-independent estimate
of a reference velocity `uRef`/`vRef` at a mixed-layer-depth-dependent
reference level `zRef` (kpp_forcing_surf.F:309-419). The Python port always
used the simple formula, silently ignoring the already-present (but
previously unwired) `KPPParameters.estimate_uref` flag -- this made `dVsq`
(and hence `Ritop`, `Rib`, and `hbl`) diverge substantially on `vermix`
(mean hbl error ~9 m over 20 timesteps) despite `shsq`/`dbloc`/the bulk-
Richardson search itself all being correct (confirmed separately by feeding
MITgcm's own `dVsq`/`Ritop`/`dbloc` into `diagnose_bl_depth` and reproducing
MITgcm's `hbl` exactly).

Feeding vermix's real capture through the fixed `_compute_shear` reduces the
mean hbl error from ~9.13 m to ~5.6e-5 m (max from 13.8 m to 1.1e-4 m); dVsq
itself matches MITgcm to floating-point roundoff (max_rel ~1.5e-15, was 631).

The two cases below independently re-derive kpp_forcing_surf.F's two branches
(log-profile estimate when zRef < drF(1); depth-weighted average when
zRef >= drF(1), including a partial-cell contribution) using plain arithmetic
written directly in this file, not by calling any driver code -- so a future
refactor of `_estimate_reference_velocity` that silently breaks the
translation will be caught here.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_parameters import KPPParameters
from KPP.kpp_core_driver import KPPDriver

TOL = 1e-9


def test_compute_shear_default_no_estimate_uref_unchanged():
    """estimate_uref=False (the default, matching every experiment except
    vermix) must keep using the plain surface-relative formula
    dvsq[k] = (u[0]-u[k])**2 + (v[0]-v[k])**2, unaffected by the new branch."""
    params = KPPParameters()
    assert params.estimate_uref is False
    driver = KPPDriver(params=params)

    u_vel = np.array([0.1, 0.08, 0.05, 0.03, 0.01])
    v_vel = np.array([0.02, 0.01, 0.0, -0.01, -0.02])
    depth = np.array([-5., -15., -25., -35., -45.])
    cell_thickness = np.full(5, 10.0)

    shsq, dvsq = driver._compute_shear(u_vel, v_vel, depth, cell_thickness)

    expected_dvsq = (u_vel[0] - u_vel) ** 2 + (v_vel[0] - v_vel) ** 2
    assert np.allclose(dvsq, expected_dvsq, atol=TOL)
    print("PASS test_compute_shear_default_no_estimate_uref_unchanged")


def test_estimate_uref_log_profile_branch():
    """Case A: zRef ends up < drF(1) (cell_thickness[0]), so uRef/vRef use
    the log-profile estimate (kpp_forcing_surf.F:383-399). No buoyancy
    crossing (dbloc*recip_drC never exceeds dB_dz) -> hMix defaults to the
    total column depth (kpp_forcing_surf.F:348-350), then epsilon*hMix=5.0
    is overridden by the larger roughness-length floor z0~5.863
    (kpp_forcing_surf.F:370-372), which is still < drF(1)=10 -> log branch.

    Expected uRef/vRef independently hand-derived (see
    /tmp/precompute_uref_test.py-style arithmetic, reproduced inline here):
    u_ref = 0.1 + (tau_x/drF(1)) * [ustar*(ln(zRef/drF1)+z0/zRef-z0/drF1)/vonk/|ustarX|]
          ~= 0.0969943087
    v_ref = 0.0 (tau_y = 0)
    """
    params = KPPParameters(estimate_uref=True)
    driver = KPPDriver(params=params)

    cell_thickness = np.full(5, 10.0)
    depth = np.array([-5., -15., -25., -35., -45.])
    dbloc = np.full(4, 1.0e-6)  # grad ~1e-7 << dB_dz=5.2e-5 everywhere: no crossing
    u_vel = np.array([0.1, 0.08, 0.05, 0.03, 0.01])
    v_vel = np.zeros(5)
    tau_x, tau_y, ustar = 1.0e-4, 0.0, 0.01

    u_ref, v_ref = driver._estimate_reference_velocity(
        u_vel, v_vel, depth, cell_thickness, dbloc, tau_x, tau_y, ustar
    )

    assert abs(u_ref - 0.0969943087) < 1e-8, f"u_ref={u_ref}"
    assert abs(v_ref - 0.0) < 1e-12, f"v_ref={v_ref}"
    print("PASS test_estimate_uref_log_profile_branch")


def test_estimate_uref_depth_average_branch():
    """Case B: a deep, fine grid (25 x 2m cells) pushes epsilon*hMix=5.0
    past drF(1)=2.0, taking the depth-weighted-average branch
    (kpp_forcing_surf.F:400-419) instead of the log-profile estimate.
    zRef=5.0 lands inside the third cell (interfaces at 0,-2,-4,-6,...), so
    the accumulation loop executes exactly once (whole second cell,
    2m*u[1]) plus a partial contribution from the third cell
    (1m*u[2], since zRef-4=1 < drF(3)=2), exercising both the while-loop
    body and the partial-cell remainder in the same case.

    Expected (hand-derived): u_ref = (0.1*2 + 2*u[1] + 1*u[2]) / 5.0 ~= 0.097
    """
    params = KPPParameters(estimate_uref=True)
    driver = KPPDriver(params=params)

    nz = 25
    cell_thickness = np.full(nz, 2.0)
    depth = -(np.cumsum(cell_thickness) - cell_thickness / 2.0)
    dbloc = np.full(nz - 1, 1.0e-6)  # no crossing -> hMix = total depth = 50
    u_vel = np.linspace(0.1, 0.01, nz)
    v_vel = np.zeros(nz)
    tau_x, tau_y, ustar = 1.0e-4, 0.0, 0.01

    u_ref, v_ref = driver._estimate_reference_velocity(
        u_vel, v_vel, depth, cell_thickness, dbloc, tau_x, tau_y, ustar
    )

    expected_u_ref = (u_vel[0] * 2.0 + 2.0 * u_vel[1] + 1.0 * u_vel[2]) / 5.0
    assert abs(u_ref - expected_u_ref) < 1e-8, f"u_ref={u_ref}, expected={expected_u_ref}"
    assert abs(v_ref - 0.0) < 1e-12, f"v_ref={v_ref}"
    print("PASS test_estimate_uref_depth_average_branch")


def test_estimate_uref_requires_tau_and_ustar():
    """KPP_ESTIMATE_UREF genuinely needs the surface momentum forcing
    (tau_x/tau_y), not just a pre-computed ustar magnitude -- Mode 1
    (pre-computed-forcing-only validation) cannot support it. This must
    fail loudly, not silently fall back to the simple formula."""
    params = KPPParameters(estimate_uref=True)
    driver = KPPDriver(params=params)

    cell_thickness = np.full(5, 10.0)
    depth = np.array([-5., -15., -25., -35., -45.])
    dbloc = np.full(4, 1.0e-6)
    u_vel = np.array([0.1, 0.08, 0.05, 0.03, 0.01])
    v_vel = np.zeros(5)

    try:
        driver._estimate_reference_velocity(
            u_vel, v_vel, depth, cell_thickness, dbloc, None, None, 0.01
        )
        assert False, "expected ValueError when tau_x/tau_y are missing"
    except ValueError:
        pass
    print("PASS test_estimate_uref_requires_tau_and_ustar")


if __name__ == "__main__":
    test_compute_shear_default_no_estimate_uref_unchanged()
    test_estimate_uref_log_profile_branch()
    test_estimate_uref_depth_average_branch()
    test_estimate_uref_requires_tau_and_ustar()
