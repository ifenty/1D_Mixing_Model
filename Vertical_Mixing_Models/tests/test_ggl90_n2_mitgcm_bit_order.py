"""
Bit-level MITgcm operation order of the GGL90 N^2 (issue 1DMIX-068).

MITgcm forms the GGL90 buoyancy frequency as

    rho'(k)   = FIND_RHO_2D(T(k), S(k), kRef=k)                  # rho - rhoConst
    rho'(k-1) = FIND_RHO_2D(T(k-1), S(k-1), kRef=k)
    sigmaR    = recip_drC * rkSign * (rho'(k) - rho'(k-1))       # grad_sigma.F:93-95
    Nsquare   = gravity*gravitySign*recip_rhoConst*sigmaR         # ggl90_calc.F:353-354

with rhoP0 = rfresh + rsalt, bulkMod = bMfresh + bMsalt + bMpres (find_rho.F) and
drC(k) = 0.5*(delR(k-1)+delR(k)) (ini_vertical_grid.F:123-127). Floating-point
addition is not associative, so a differently-associated (mathematically
identical) sum moves rho by ~1 ulp (2.3e-13 kg/m^3) in about half of all cells.
In a near-neutral cell at the TKE floor N^2 IS one such quantum, so the port's
Ri = N^2/GGL90eps crossed the 0.2 Prandtl threshold that MITgcm's did not.

The witnesses below are real cells of the 1DMIX-066 attempt-A capture
(1D_ocean_ice_column, 11,000 steps, minimal data.ggl90). T, S, sigma_r,
ri_number and vertical_shear are the values MITgcm printed (16 significant
digits, FORMAT E25.16), so expected values are the captured sigma_r / Ri, not
anything recomputed by the port. Tolerance 1e-14 relative is the print
precision of the captured numbers (5e-16 relative) with margin; one density
quantum in these cells is a 1e-3 to 100% change of N^2, so any operation-order
regression is detected far above it.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main.eos import compute_ggl90_buoyancy_frequency_squared, jmd95_eos

GRAVITY = 9.8156           # attempt-A capture attrs: gravity
RHO_CONST = 1027.0         # attempt-A capture attrs: rhoConst
GGL90_EPS = 2.23e-16       # MITgcm GGL90eps default
RECIP_RHO = 1.0 / RHO_CONST
N2_PREFACTOR = (GRAVITY * -1.0) * RECIP_RHO   # gravity*gravitySign*recip_rhoConst

# Bottom two levels of the 23-level column: centres and layer thicknesses.
BOTTOM_DEPTH = np.array([-409.93, -477.47])
BOTTOM_DELR = np.array([63.5, 71.58])
# Levels 2,3 (top of the stratified region).
UPPER_DEPTH = np.array([-25.0, -35.0])
UPPER_DELR = np.array([10.0, 10.0])

# (time step, T[k-1], T[k], S[k-1], S[k], sigma_r[k], ri_number[k], vertical_shear[k])
# bottom face k=22. MITgcm's own Ri is 0.1443; the pre-fix port gave N^2 twice as large
# (6.435e-17 vs MITgcm 3.2175e-17) and Ri = 0.2886, across the 0.2 Prandtl threshold.
BOTTOM_WITNESSES = [
    (3, 0.4999999999990205, 0.4999999999999998, 34.79999999999966, 34.79999999999998,
     -3.366503930163341e-15, 0.1442848296746206, 4.885048099745647e-153),
    (9, 0.4999999999987123, 0.4999999999999997, 34.79999999999953, 34.79999999999998,
     -3.366503930163341e-15, 0.1442848296746206, 2.019905064851982e-139),
    (20, 0.4999999999974098, 0.4999999999999998, 34.79999999999904, 34.79999999999998,
     -3.366503930163341e-15, 0.1442848296746206, 6.742885940112248e-128),
]

# (time step, T[k-1], T[k], S[k-1], S[k], sigma_r[k]) at k=3. The pre-fix port was
# off by 1e-10 relative here (one-ulp-of-rho difference); MITgcm-order is 1e-16.
UPPER_WITNESSES = [
    (52, -1.793616337781301, -1.72889394417397, 29.07867946639834, 29.07740208873614,
     0.0001701449930124),
    (66, -1.846075341615911, -1.82239762976331, 29.08132077312309, 29.08021032284485,
     0.0001119065987836621),
    (78, -1.882023251681028, -1.867833193079842, 29.08602992978902, 29.08420472044905,
     0.0001604286235988184),
]


def _n2(theta, salt, depth, delr):
    return compute_ggl90_buoyancy_frequency_squared(
        np.array(theta), np.array(salt), depth, RHO_CONST, GRAVITY, True, cell_thickness=delr
    )[1]


@pytest.mark.parametrize('witness', BOTTOM_WITNESSES, ids=lambda w: f't{w[0]}')
def test_bottom_face_n2_and_ri_match_mitgcm_capture(witness):
    """Near-neutral bottom face: N^2 and Ri equal MITgcm's captured values; Ri < 0.2 branch."""
    _, tm, tk, sm, sk, sigma_r, ri_mit, shear = witness
    n2 = _n2([tm, tk], [sm, sk], BOTTOM_DEPTH, BOTTOM_DELR)
    n2_mit = N2_PREFACTOR * sigma_r          # what MITgcm's ggl90_calc.F:353 forms from its sigmaR
    assert n2 == pytest.approx(n2_mit, rel=1e-14, abs=0.0), (n2, n2_mit)
    ri = max(n2, 0.0) / (shear + GGL90_EPS)  # ggl90_calc.F:581, RiNumber
    assert ri == pytest.approx(ri_mit, rel=1e-14, abs=0.0), (ri, ri_mit)
    # the point of 1DMIX-068: same side of the 0.2 Prandtl threshold as MITgcm
    assert (ri > 0.2) == (ri_mit > 0.2)
    assert ri < 0.2


@pytest.mark.parametrize('witness', UPPER_WITNESSES, ids=lambda w: f't{w[0]}')
def test_interior_face_n2_matches_mitgcm_capture(witness):
    _, tm, tk, sm, sk, sigma_r = witness
    n2 = _n2([tm, tk], [sm, sk], UPPER_DEPTH, UPPER_DELR)
    assert n2 == pytest.approx(N2_PREFACTOR * sigma_r, rel=1e-14, abs=0.0)


def _mitgcm_find_rho(t, s, loc_pres_pa):
    """Independent statement of find_rho.F FIND_RHO_2D, JMD95 branch (non-factorised), rho - rhoConst."""
    t2 = t * t; t3 = t2 * t; t4 = t3 * t
    s3o2 = s * np.sqrt(s)
    rfresh = (999.842594 + 6.793952e-02 * t - 9.095290e-03 * t2 + 1.001685e-04 * t3
              - 1.120083e-06 * t4 + 6.536332e-09 * t4 * t)
    rsalt = (s * (8.24493e-01 - 4.0899e-03 * t + 7.6438e-05 * t2 - 8.2467e-07 * t3 + 5.3875e-09 * t4)
             + s3o2 * (-5.72466e-03 + 1.0227e-04 * t - 1.6546e-06 * t2)
             + 4.8314e-04 * s * s)
    rhop0 = rfresh + rsalt
    p = loc_pres_pa * 1.0e-5
    p2 = p * p
    bmf = 1.965933e+04 + 1.444304e+02 * t - 1.706103e+00 * t2 + 9.648704e-03 * t3 - 4.190253e-05 * t4
    bms = (s * (5.284855e+01 - 3.101089e-01 * t + 6.283263e-03 * t2 - 5.084188e-05 * t3)
           + s3o2 * (3.886640e-01 + 9.085835e-03 * t - 4.619924e-04 * t2))
    bmp = (p * (3.186519e+00 + 2.212276e-02 * t - 2.984642e-04 * t2 + 1.956415e-06 * t3)
           + p * s * (6.704388e-03 - 1.847318e-04 * t + 2.059331e-07 * t2)
           + p * s3o2 * 1.480266e-04
           + p2 * (2.102898e-04 - 1.202016e-05 * t + 1.394680e-07 * t2)
           + p2 * s * (-2.040237e-06 + 6.128773e-08 * t + 6.207323e-10 * t2))
    return rhop0 / (1.0 - loc_pres_pa * 1.0e-5 / (bmf + bms + bmp)) - RHO_CONST


def _mitgcm_reference_n2(theta, salt, delr):
    """grad_sigma.F + ggl90_calc.F Nsquare, level by level, in MITgcm's operation order.

    theta/salt have shape (ncol, nz); returns (Nsquare (ncol, nz), rC (nz,)).
    """
    nz = theta.shape[1]
    rc = np.zeros(nz)                                   # ini_vertical_grid.F rC recurrence, rkSign=-1
    rc[0] = 0.0 + -1.0 * (0.5 * delr[0])
    for k in range(1, nz):
        rc[k] = rc[k - 1] + -1.0 * (0.5 * (delr[k - 1] + delr[k]))
    pref = 0.0 + RHO_CONST * (rc - 0.0) * GRAVITY * -1.0  # set_ref_state.F:96-97 [Pa]
    out = np.zeros(theta.shape)
    for k in range(1, nz):
        recip_drc = 1.0 / (0.5 * (delr[k - 1] + delr[k]))
        sig = recip_drc * -1.0 * (_mitgcm_find_rho(theta[:, k], salt[:, k], pref[k])
                                  - _mitgcm_find_rho(theta[:, k - 1], salt[:, k - 1], pref[k]))
        out[:, k] = GRAVITY * -1.0 * RECIP_RHO * sig
    return out, rc


def test_column_n2_is_bit_identical_to_independent_mitgcm_order_reference():
    """Many random stable columns, every face, exact equality (not a tolerance).

    3000 columns x 22 faces = 66,000 faces: enough that even the rarest
    operation-order differences (pressure conversion, bulk-modulus
    association: each flips a density quantum in ~0.05-0.1% of cells) appear
    dozens of times, so any of them being undone fails this test.
    """
    rng = np.random.default_rng(68)
    delr = np.array([10.0] * 7 + [10.01, 10.03, 10.11, 10.32, 10.8, 11.76, 13.42, 16.04, 19.82,
                                  24.85, 31.1, 38.42, 46.5, 55.0, 63.5, 71.58])
    nz = len(delr)
    ncol = 3000
    theta = np.sort(rng.uniform(-1.9, 12.0, (ncol, nz)), axis=1)[:, ::-1] + rng.normal(0, 1e-3, (ncol, nz))
    salt = np.sort(rng.uniform(29.0, 35.5, (ncol, nz)), axis=1) + rng.normal(0, 1e-3, (ncol, nz))
    ref, rc = _mitgcm_reference_n2(theta, salt, delr)
    got = np.array([
        compute_ggl90_buoyancy_frequency_squared(
            theta[c], salt[c], rc, RHO_CONST, GRAVITY, True, cell_thickness=delr
        )
        for c in range(ncol)
    ])
    assert np.array_equal(got, ref), f'{int((got != ref).sum())} of {got.size} faces differ from the MITgcm-order reference'


def test_depth_difference_fallback_agrees_to_rounding_only():
    """Without cell_thickness drC = depth[k-1]-depth[k] (equal to ~1 ulp): physical value unchanged."""
    delr = np.array([10.0, 10.0, 10.01, 10.03])
    depth = np.array([-5.0, -15.0, -25.005, -35.025])  # rC recurrence for this delR
    theta = np.array([2.0, 1.5, 1.2, 1.0]); salt = np.array([34.0, 34.1, 34.2, 34.3])
    a = compute_ggl90_buoyancy_frequency_squared(theta, salt, depth, RHO_CONST, GRAVITY, True)
    b = compute_ggl90_buoyancy_frequency_squared(theta, salt, depth, RHO_CONST, GRAVITY, True, cell_thickness=delr)
    np.testing.assert_allclose(a, b, rtol=1e-8)


def test_jmd95_pressure_bar_override_is_backward_compatible():
    """Default path unchanged (0.1*pressure); pressure_bar=0.1*pressure reproduces it exactly."""
    t = np.array([3.0, 10.0]); s = np.array([35.5, 34.0]); p = np.array([3000.0, 500.0])
    a = jmd95_eos(t, s, p, RHO_CONST)
    b = jmd95_eos(t, s, p, RHO_CONST, pressure_bar=0.1 * p)
    for x, y in zip(a, b):
        assert np.array_equal(x, y)
    # JMD95 check value (Jackett & McDougall 1995): S=35.5, theta=3, p=3000 dbar -> 1041.83267
    rho, _, _ = jmd95_eos(np.array([3.0]), np.array([35.5]), np.array([3000.0]), 1029.0)
    assert rho[0] + 1029.0 == pytest.approx(1041.83267, abs=1e-5)
