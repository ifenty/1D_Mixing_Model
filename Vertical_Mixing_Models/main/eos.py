"""
Equation of state and buoyancy calculations.

Implements density, thermal expansion, and haline contraction computations.
Completely independent of mixing scheme - physical constants passed as parameters.
"""

import numpy as np
from typing import Optional, Tuple

# The jmd95 polynomial fit is only valid over roughly -2 to 40 degC. Without a
# sea-ice model, nothing stops a column's surface temperature from cooling far
# below the physical freezing point (~-1.9 degC) if mixing can't keep pace with
# surface heat loss. Extrapolating the polynomial that far outside its fitted
# range is not just inaccurate -- it is non-monotonic (density can turn over
# and DECREASE with further cooling), which spuriously makes ultra-cold water
# look buoyant/stable and can shut off convective mixing entirely, causing a
# runaway feedback. Clamp the temperature seen by the EOS to this floor (the
# real physical response at this point would be sea-ice formation, which this
# model does not represent).
EOS_MIN_THETA_C = -2.0


def _depth_to_eos_pressure(
    depth: np.ndarray,
    rho_const: float,
    gravity: float,
) -> np.ndarray:
    """
    Convert depth (negative-down, metres) to the `pressure` argument expected
    by `jmd95_eos` (which internally does `p_bar = 0.1 * pressure`).

    This reproduces MITgcm's real EOS pressure for the model's default,
    non-iterative reference-pressure branch -- `selectP_inEOS_Zc<=1`, no
    `gravityFile`/`integr_GeoPot`, `top_Pres=0`, `seaLev_Z=0`, `surf_pRef ==
    eosRefP0` -- confirmed at runtime for every experiment currently captured
    by this project (`1D_ocean_ice_column`, `lab_sea`, `vermix`,
    `global_oce_latlon`, `seaice_obcs`, `isomip`; see closed issue 1DMIX-039):

        - `model/src/set_ref_state.F:118-121`: `pRef4EOS(k) = top_Pres +
          rhoConst*gravity*gravitySign*(rC(k)-rF(1))`, which reduces to
          `pRef4EOS(k) = rhoConst*gravity*depth(k)` [Pa] for the above
          defaults (`gravitySign=-1` for z-coordinates,
          `model/src/ini_vertical_grid.F:54`).
        - `model/src/pressure_for_eos.F` (`selectP_inEOS_Zc.LE.1` branch):
          `locPres(k) = pRef4EOS(k) + dpRef`, `dpRef = surf_pRef - eosRefP0
          = 0` under the above defaults.
        - `model/inc/EOS.h:19` / `model/src/find_rho.F:507`:
          `p_bar = locPres(k) * SItoBar`, `SItoBar = 1e-5`.

    So MITgcm's real bar-per-metre-of-depth conversion factor is
    `rho_const*gravity*1e-5`, NOT a flat `0.1` -- the previous port hardcoded
    `p_bar = 0.1*(-depth)` (equivalent to assuming `rho_const*gravity ==
    1e4`, i.e. `rho_const ~= 1019.4` for `gravity=9.81`), independent of the
    model's actual `rho_const`/`gravity`. That mismatch is exact-zero at the
    surface (p=0) and grows linearly with depth, entering only the
    pressure-dependent bulk-modulus terms -- confirmed (1DMIX-039 evidence)
    to reproduce the previously-unexplained ~1e-5-1e-4 relative, depth-
    growing N² discrepancy against MITgcm's real `isomip` capture, and to
    collapse that discrepancy to floating-point noise (~1e-12 relative or
    smaller) once corrected.

    Returns the value to pass as `jmd95_eos`'s `pressure` argument (which
    that function multiplies by 0.1 to get bar), i.e.
    `rho_const*gravity*1e-4*(-depth)`.
    """
    return (-depth) * rho_const * gravity * 1.0e-4


def _mitgcm_eos_pressure_bar(
    depth: np.ndarray,
    rho_const: float,
    gravity: float,
) -> np.ndarray:
    """
    EOS pressure in bar, with MITgcm's exact floating-point operation order.

    Same physical value as `_depth_to_eos_pressure(...) * 0.1` (see that
    function for the default-branch conditions), but formed the way MITgcm
    does, for callers that need bit-level agreement (1DMIX-068):

        - `model/src/set_ref_state.F:96-97`: `pRef4EOS(k) = pRefIntF(1) +
          rhoConst*(rC(k)-rF(1))*gravity*gravitySign` [Pa], evaluated left to
          right with `pRefIntF(1)=top_Pres=0`, `rF(1)=0`, `gravitySign=-1`;
        - `model/src/find_rho.F` (FIND_RHO_2D/FIND_BULKMOD): `p =
          locPres*SItoBar`, `SItoBar = 1.D-05` (`model/inc/EOS.h:19`).

    `_depth_to_eos_pressure(...)` followed by `jmd95_eos`'s own `0.1*` gives
    the same number only to ~1 ulp; that ulp was enough to move one
    density quantum in ~0.05% of near-neutral cells.
    """
    loc_pres_pa = 0.0 + rho_const * (depth - 0.0) * gravity * -1.0
    return loc_pres_pa * 1.0e-5


def linear_eos(
    theta: np.ndarray,
    salt: np.ndarray,
    depth: np.ndarray,
    rho_const: float = 1029.0,
    tref: float = 20.0,
    sref: float = 35.0,
    alpha: float = 2.0e-4,
    beta: float = 7.4e-4,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Linear equation of state for testing.

    rho = rho0 * (1 - alpha*(T-Tref) + beta*(S-Sref))

    Parameters
    ----------
    theta : np.ndarray
        Potential temperature [°C]
    salt : np.ndarray
        Salinity [psu or g/kg]
    depth : np.ndarray
        Signed cell-centre z [m], negative and more negative downward, as
        ColumnGrid.depth (MITgcm wording convention "depth positive down"
        refers to -depth). Unused by this linear formula.
    rho_const : float
        Reference density [kg/m^3]
    tref : float
        Reference temperature [°C]
    sref : float
        Reference salinity [psu]
    alpha : float
        Thermal expansion coefficient [1/°C]
    beta : float
        Haline contraction coefficient [psu^-1]

    Returns
    -------
    rho : np.ndarray
        Density anomaly [kg/m^3]
    ttalpha : np.ndarray
        d(rho)/d(theta) without 1/rho factor [kg/m^3/°C]
    ssbeta : np.ndarray
        d(rho)/d(salt) without 1/rho factor [kg/m^3/psu]
    """
    # Density anomaly
    drho = -alpha * (theta - tref) + beta * (salt - sref)
    rho = rho_const * (1.0 + drho)

    # Thermal expansion and haline contraction
    ttalpha = -alpha * rho_const * np.ones_like(theta)
    ssbeta = beta * rho_const * np.ones_like(salt)

    return rho - rho_const, ttalpha, ssbeta


def jmd95_eos(
    theta: np.ndarray,
    salt: np.ndarray,
    pressure: np.ndarray,
    rho_const: float = 1029.0,
    *,
    pressure_bar: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Jackett and McDougall (1995) equation of state.

    This is the standard EOS used in MITgcm. Implementation follows
    MITgcm/utils/matlab/densjmd95.m

    Parameters
    ----------
    theta : np.ndarray
        Potential temperature [°C (IPTS-68)]
    salt : np.ndarray
        Salinity [psu (PSS-78)]
    pressure : np.ndarray
        Pressure [dbar] (approximately depth in m * 10)
    rho_const : float
        Reference density [kg/m^3] for anomaly calculation
    pressure_bar : np.ndarray, optional (keyword-only)
        If given, the pressure in bar, used as-is instead of ``0.1 *
        pressure``. Lets a caller supply MITgcm's exact ``locPres*SItoBar``
        (see ``_mitgcm_eos_pressure_bar``, 1DMIX-068); ``pressure`` is then
        ignored. Default ``None`` keeps the historical ``0.1 * pressure``.

    Returns
    -------
    rho : np.ndarray
        Density anomaly relative to rho_const [kg/m^3]
    ttalpha : np.ndarray
        d(rho)/d(theta) without 1/rho factor [kg/m^3/°C]
    ssbeta : np.ndarray
        d(rho)/d(salt) without 1/rho factor [kg/m^3/psu]

    Notes
    -----
    Check value: S=35.5, Theta=3, P=3000 → rho=1041.83267 kg/m³
    """
    # Ensure all inputs are arrays
    t = np.atleast_1d(theta)
    s = np.atleast_1d(salt)
    p = np.atleast_1d(pressure)

    # Clamp to the EOS's valid range (see EOS_MIN_THETA_C above) -- prevents
    # non-monotonic extrapolation artifacts at extreme sub-freezing
    # temperatures that this model has no sea-ice process to actually produce.
    t = np.maximum(t, EOS_MIN_THETA_C)

    # Convert pressure from dbar to bar (or take the caller's exact bar value)
    if pressure_bar is None:
        p = 0.1 * p
    else:
        p = np.atleast_1d(pressure_bar)

    # Precompute powers
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    s3o2 = s * np.sqrt(s)
    p2 = p * p

    # Coefficients for density of fresh water at p=0
    eosJMDCFw = np.array([
        999.842594,
        6.793952e-02,
       -9.095290e-03,
        1.001685e-04,
       -1.120083e-06,
        6.536332e-09
    ])

    # Coefficients for density of sea water at p=0
    eosJMDCSw = np.array([
        8.244930e-01,
       -4.089900e-03,
        7.643800e-05,
       -8.246700e-07,
        5.387500e-09,
       -5.724660e-03,
        1.022700e-04,
       -1.654600e-06,
        4.831400e-04
    ])

    # Density of fresh water at surface
    rho_fresh = (eosJMDCFw[0]
                 + eosJMDCFw[1] * t
                 + eosJMDCFw[2] * t2
                 + eosJMDCFw[3] * t3
                 + eosJMDCFw[4] * t4
                 + eosJMDCFw[5] * t4 * t)

    # Density of sea water at surface. The salt terms are summed FIRST and
    # then added to the fresh-water density, exactly MITgcm's
    # FIND_RHOP0 (model/src/find_rho.F): `rsalt = s*(..) + s3o2*(..) +
    # c9*s*s ; rhoP0 = rfresh + rsalt`. Floating-point addition is not
    # associative, and the previous left-to-right form
    # `((rho_fresh + s*(..)) + s3o2*(..)) + c9*s*s` differed from MITgcm by
    # ~1 ulp of rho in about half of all cells -- invisible in aggregate
    # stats, but the bit-level difference decides the Prandtl branch in
    # near-neutral cells at the TKE floor, where N^2 is itself one density
    # quantum (1DMIX-068).
    rho_salt = (s * (eosJMDCSw[0]
                     + eosJMDCSw[1] * t
                     + eosJMDCSw[2] * t2
                     + eosJMDCSw[3] * t3
                     + eosJMDCSw[4] * t4)
                + s3o2 * (eosJMDCSw[5]
                          + eosJMDCSw[6] * t
                          + eosJMDCSw[7] * t2)
                + eosJMDCSw[8] * s * s)
    rho_surf = rho_fresh + rho_salt

    # Bulk modulus
    bulkmod = _bulkmod_jmd95(s, t, p, t2, t3, t4, s3o2, p2)

    # In-situ density [kg/m³]
    rho = rho_surf / (1.0 - p / bulkmod)

    # Return anomaly relative to rhoConst. This reference is bookkeeping only:
    # callers add it straight back (rho = rho_anom + rho_const) to recover the
    # full in-situ density, so the choice of reference cancels and does not
    # affect any physical result (the check value 1041.83267 is unchanged).
    rho_anom = rho - rho_const

    # Thermal expansion coefficient d(rho)/d(T)
    # Derivative of density at surface
    drho_dt_fresh = (eosJMDCFw[1]
                     + 2.0 * eosJMDCFw[2] * t
                     + 3.0 * eosJMDCFw[3] * t2
                     + 4.0 * eosJMDCFw[4] * t3
                     + 5.0 * eosJMDCFw[5] * t4)

    drho_dt_surf = (drho_dt_fresh
                    + s * (eosJMDCSw[1]
                           + 2.0 * eosJMDCSw[2] * t
                           + 3.0 * eosJMDCSw[3] * t2
                           + 4.0 * eosJMDCSw[4] * t3)
                    + s3o2 * (eosJMDCSw[6]
                              + 2.0 * eosJMDCSw[7] * t))

    # Derivative of bulk modulus
    dbulkmod_dt = _dbulkmod_dt_jmd95(s, t, p, t2, t3, s3o2, p2)

    # Chain rule for in-situ density derivative. Matches MITgcm FIND_ALPHA's
    # JMD95 branch (model/src/find_alpha.F:214-218):
    #   alphaLoc = (K^2*A - K*p*A - rhoP0*p*B) / (K-p)^2
    #            = A*K/(K-p) - rhoP0*p*B/(K-p)^2
    # (K=bulkmod, A=drhoP0dtheta, B=dKdtheta). The previous form here used
    # `+ ... / (bulkmod * (bulkmod - p))` -- wrong sign AND wrong denominator
    # on the second term; exact at p=0 but diverging from a finite-difference
    # check with increasing pressure (ratio 1.0 at p=0 -> 0.115 at p=4000 dbar
    # for a representative theta/salt point), see closed issue 1DMIX-017.
    ttalpha = drho_dt_surf * bulkmod / (bulkmod - p) - rho_surf * p * dbulkmod_dt / (bulkmod - p) ** 2

    # Haline contraction coefficient d(rho)/d(S)
    s_sqrt = np.sqrt(s)

    drho_ds_surf = (eosJMDCSw[0]
                    + eosJMDCSw[1] * t
                    + eosJMDCSw[2] * t2
                    + eosJMDCSw[3] * t3
                    + eosJMDCSw[4] * t4
                    + 1.5 * s_sqrt * (eosJMDCSw[5]
                                      + eosJMDCSw[6] * t
                                      + eosJMDCSw[7] * t2)
                    + 2.0 * eosJMDCSw[8] * s)

    # Derivative of bulk modulus w.r.t. salinity
    dbulkmod_ds = _dbulkmod_ds_jmd95(s, t, p, t2, s_sqrt, p2)

    # Chain rule for in-situ density derivative. Same correction as ttalpha
    # above, mirroring MITgcm FIND_BETA's JMD95 branch (find_alpha.F:531-535).
    ssbeta = drho_ds_surf * bulkmod / (bulkmod - p) - rho_surf * p * dbulkmod_ds / (bulkmod - p) ** 2

    return rho_anom, ttalpha, ssbeta


def _bulkmod_jmd95(s, t, p, t2, t3, t4, s3o2, p2):
    """Secant bulk modulus for JMD95 EOS."""
    # Coefficients for bulk modulus of fresh water at p=0
    eosJMDCKFw = np.array([
        1.965933e+04,
        1.444304e+02,
       -1.706103e+00,
        9.648704e-03,
       -4.190253e-05
    ])

    # Coefficients for bulk modulus of sea water at p=0
    eosJMDCKSw = np.array([
        5.284855e+01,
       -3.101089e-01,
        6.283263e-03,
       -5.084188e-05,
        3.886640e-01,
        9.085835e-03,
       -4.619924e-04
    ])

    # Coefficients for bulk modulus at pressure p
    eosJMDCKP = np.array([
        3.186519e+00,
        2.212276e-02,
       -2.984642e-04,
        1.956415e-06,
        6.704388e-03,
       -1.847318e-04,
        2.059331e-07,
        1.480266e-04,
        2.102898e-04,
       -1.202016e-05,
        1.394680e-07,
       -2.040237e-06,
        6.128773e-08,
        6.207323e-10
    ])

    # Bulk modulus of fresh water at surface
    bulkmod_fresh = (eosJMDCKFw[0]
                     + eosJMDCKFw[1] * t
                     + eosJMDCKFw[2] * t2
                     + eosJMDCKFw[3] * t3
                     + eosJMDCKFw[4] * t4)

    # Bulk modulus of sea water at surface (salt terms only; combined with
    # the fresh-water part below exactly as MITgcm's FIND_BULKMOD does).
    bulkmod_salt = (s * (eosJMDCKSw[0]
                         + eosJMDCKSw[1] * t
                         + eosJMDCKSw[2] * t2
                         + eosJMDCKSw[3] * t3)
                    + s3o2 * (eosJMDCKSw[4]
                              + eosJMDCKSw[5] * t
                              + eosJMDCKSw[6] * t2))

    # Pressure-dependent part of the secant bulk modulus (MITgcm `bMpres`)
    bulkmod_pres = (p * (eosJMDCKP[0]
                         + eosJMDCKP[1] * t
                         + eosJMDCKP[2] * t2
                         + eosJMDCKP[3] * t3)
                    + p * s * (eosJMDCKP[4]
                               + eosJMDCKP[5] * t
                               + eosJMDCKP[6] * t2)
                    + p * s3o2 * eosJMDCKP[7]
                    + p2 * (eosJMDCKP[8]
                            + eosJMDCKP[9] * t
                            + eosJMDCKP[10] * t2)
                    + p2 * s * (eosJMDCKP[11]
                                + eosJMDCKP[12] * t
                                + eosJMDCKP[13] * t2))

    # MITgcm (find_rho.F FIND_BULKMOD): bulkMod = bMfresh + bMsalt + bMpres,
    # three group sums added last -- not a single running left-to-right sum
    # (1DMIX-068: association order is a bit-level, ulp-of-rho effect).
    bulkmod = bulkmod_fresh + bulkmod_salt + bulkmod_pres

    return bulkmod


def _dbulkmod_dt_jmd95(s, t, p, t2, t3, s3o2, p2):
    """Derivative of bulk modulus w.r.t. temperature."""
    # Coefficients (same as in _bulkmod_jmd95)
    eosJMDCKFw = np.array([0, 1.444304e+02, -1.706103e+00, 9.648704e-03, -4.190253e-05])
    eosJMDCKSw = np.array([0, -3.101089e-01, 6.283263e-03, -5.084188e-05, 0, 9.085835e-03, -4.619924e-04])
    eosJMDCKP = np.array([0, 2.212276e-02, -2.984642e-04, 1.956415e-06, 0, -1.847318e-04, 2.059331e-07, 0, 0, -1.202016e-05, 1.394680e-07, 0, 6.128773e-08, 6.207323e-10])

    dbulkmod_dt = (eosJMDCKFw[1]
                   + 2.0 * eosJMDCKFw[2] * t
                   + 3.0 * eosJMDCKFw[3] * t2
                   + 4.0 * eosJMDCKFw[4] * t3
                   + s * (eosJMDCKSw[1]
                          + 2.0 * eosJMDCKSw[2] * t
                          + 3.0 * eosJMDCKSw[3] * t2)
                   + s3o2 * (eosJMDCKSw[5]
                             + 2.0 * eosJMDCKSw[6] * t)
                   + p * (eosJMDCKP[1]
                          + 2.0 * eosJMDCKP[2] * t
                          + 3.0 * eosJMDCKP[3] * t2)
                   + p * s * (eosJMDCKP[5]
                              + 2.0 * eosJMDCKP[6] * t)
                   + p2 * (eosJMDCKP[9]
                           + 2.0 * eosJMDCKP[10] * t)
                   + p2 * s * (eosJMDCKP[12]
                               + 2.0 * eosJMDCKP[13] * t))

    return dbulkmod_dt


def _dbulkmod_ds_jmd95(s, t, p, t2, s_sqrt, p2):
    """Derivative of bulk modulus w.r.t. salinity."""
    eosJMDCKSw = np.array([5.284855e+01, -3.101089e-01, 6.283263e-03, -5.084188e-05, 3.886640e-01, 9.085835e-03, -4.619924e-04])
    eosJMDCKP = np.array([0, 0, 0, 0, 6.704388e-03, -1.847318e-04, 2.059331e-07, 1.480266e-04, 0, 0, 0, -2.040237e-06, 6.128773e-08, 6.207323e-10])

    dbulkmod_ds = (eosJMDCKSw[0]
                   + eosJMDCKSw[1] * t
                   + eosJMDCKSw[2] * t2
                   + eosJMDCKSw[3] * t2 * t
                   + 1.5 * s_sqrt * (eosJMDCKSw[4]
                                     + eosJMDCKSw[5] * t
                                     + eosJMDCKSw[6] * t2)
                   + p * (eosJMDCKP[4]
                          + eosJMDCKP[5] * t
                          + eosJMDCKP[6] * t2)
                   + p * 1.5 * s_sqrt * eosJMDCKP[7]
                   + p2 * (eosJMDCKP[11]
                           + eosJMDCKP[12] * t
                           + eosJMDCKP[13] * t2))

    return dbulkmod_ds


def compute_static_instability_mask(
    theta: np.ndarray,
    salt: np.ndarray,
    depth: np.ndarray,
    rho_const: float = 1029.0,
    gravity: float = 9.81,
) -> np.ndarray:
    """
    Flag statically unstable interfaces (denser water directly overlying
    lighter water), for a scheme-independent convective-adjustment step
    (MITgcm's `ivdc_kappa`, see calc_ivdc.F / convective_weights.F).

    MITgcm's own instability test only depends on the SIGN of the density
    gradient (`-sigmaR*gravitySign > 0`), not on any particular scaling of
    N^2, so the *output* needs no gravity/rho0 scaling -- but the EOS
    pressure ARGUMENT fed to each level's own in-situ density still does
    (see `_depth_to_eos_pressure`, 1DMIX-039); `gravity` is threaded through
    for that reason only.

    Parameters
    ----------
    theta : np.ndarray, shape (nz,)
        Potential temperature profile [°C], cell centers
    salt : np.ndarray, shape (nz,)
        Salinity profile [psu], cell centers
    depth : np.ndarray, shape (nz,)
        Depth of cell centers (negative, increasing downward) [m] -- e.g.
        ColumnGrid.depth
    rho_const : float
        Reference density [kg/m^3]
    gravity : float
        Gravitational acceleration [m/s^2] -- used only for the EOS pressure
        argument (see `_depth_to_eos_pressure`), not for output scaling.

    Returns
    -------
    unstable : np.ndarray of bool, shape (nz,)
        True at interface k (top face of cell k, between cells k-1 and k)
        where cell k-1 (shallower) is denser than cell k (deeper). Index 0
        (surface face) is always False.
    """
    pressure = _depth_to_eos_pressure(depth, rho_const, gravity)
    rho_anom, _, _ = jmd95_eos(theta, salt, pressure, rho_const)
    rho = rho_anom + rho_const

    nz = len(theta)
    unstable = np.zeros(nz, dtype=bool)
    unstable[1:] = rho[:-1] > rho[1:]
    return unstable


def compute_buoyancy_gradients(
    theta: np.ndarray,
    salt: np.ndarray,
    depth: np.ndarray,
    rho_const: float = 1029.0,
    gravity: float = 9.81,
    use_jmd95: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute buoyancy-related quantities for mixing schemes.

    Parameters
    ----------
    theta : np.ndarray, shape (nz,)
        Potential temperature profile [°C]
    salt : np.ndarray, shape (nz,)
        Salinity profile [psu]
    depth : np.ndarray, shape (nz,)
        Depth of cell centers (negative, increasing downward) [m]
    rho_const : float
        Reference density [kg/m^3]
    gravity : float
        Gravitational acceleration [m/s^2]
    use_jmd95 : bool
        If True, use JMD95 EOS; if False, use linear EOS

    Returns
    -------
    rho_surf : float
        Surface density [kg/m^3]
    dbloc : np.ndarray, shape (nz,)
        Local buoyancy gradient at interfaces [m/s^2]
    dbsfc : np.ndarray, shape (nz,)
        Buoyancy difference from surface [m/s^2]
    ttalpha : np.ndarray, shape (nz,)
        Thermal expansion coefficient [kg/m^3/°C]
    ssbeta : np.ndarray, shape (nz,)
        Haline contraction coefficient [kg/m^3/psu]
    """
    nz = len(theta)

    # Pressure at each cell centre, matching MITgcm's real EOS pressure
    # exactly (not a flat "1 dbar per metre") -- see `_depth_to_eos_pressure`
    # for the full `pRef4EOS`/`SItoBar` derivation and 1DMIX-039 for the
    # ~1e-5-1e-4 relative N²/density error this fixes relative to the
    # previous flat-`0.1`-bar/m version.
    #
    # NOTE (older bug fix, still applicable): the port before that used
    # `-depth / 10.0`, which is a factor of 10 too small (it would put
    # 1000 m at only 100 dbar). That under-stated the compressibility
    # correction in the EOS -- see closed issue 1DMIX-002.
    pressure = _depth_to_eos_pressure(depth, rho_const, gravity)

    if use_jmd95:
        # In-situ density anomaly + expansion coefficients, each cell at its
        # own pressure. This mirrors MITgcm FIND_ALPHA/FIND_BETA (kRef=k) for
        # ttalpha/ssbeta, which are used only for the surface buoyancy forcing.
        rho_anom, ttalpha, ssbeta = jmd95_eos(theta, salt, pressure, rho_const)
    else:
        rho_anom, ttalpha, ssbeta = linear_eos(theta, salt, -depth, rho_const)

    rho = rho_anom + rho_const  # full in-situ density [kg/m^3]

    # Surface density
    rho_surf = rho[0]

    # ------------------------------------------------------------------
    # Local buoyancy gradient dbloc and surface buoyancy difference dbsfc.
    #
    # This reproduces MITgcm statekpp (kpp_routines.F:1930-1933):
    #     DBLOC(k-1) = g*(RHOK - RHOKM1)/(RHOK + rhoConst)
    #     DBSFC(k)   = g*(RHOK - RHO1K )/(RHOK + rhoConst)
    # where RHOK (deeper), RHOKM1 (shallower) and RHO1K (surface T/S) are ALL
    # evaluated at a SINGLE reference pressure -- the pressure of the deeper
    # level k (FIND_RHO_2D is called with the same kRef for all three). Using a
    # common reference pressure removes the compressibility contribution, so the
    # difference reflects only the adiabatic (potential) density contrast that
    # actually drives buoyancy. RHOK etc. are density *anomalies* relative to
    # rhoConst, so (RHOK + rhoConst) is the full in-situ density of the deeper
    # cell -- the correct denominator (NOT full + rhoConst).
    #
    # TWO bugs are fixed here relative to the previous port, both of which made
    # this a Python porting error (the Fortran is correct):
    #   1. SIGN: it computed (rho[k]-rho[k+1]) = shallower-minus-deeper, which is
    #      negative under stable stratification. It must be deeper-minus-shallower
    #      so that dbloc > 0 for stable water. The inverted sign made the interior
    #      Richardson-number and convection functions fire backwards, giving
    #      ~0.1 m^2/s diffusivity in a stable column instead of ~1e-5.
    #   2. DENOMINATOR: it divided by (rho[k+1] + rho_const) ~ 2070, double
    #      counting rhoConst (rho[k+1] is already the full in-situ density).
    #      That halved every buoyancy gradient.
    # Neither behaviour exists in MITgcm; correcting them is exactly how we
    # reproduce the reference solution, so no keep_mitgcm_bugs gate is needed.
    # ------------------------------------------------------------------
    dbloc = np.zeros(nz)
    dbsfc = np.zeros(nz)

    if use_jmd95:
        # dbloc[k]: interface between shallower cell k and deeper cell k+1.
        # Reference pressure = deeper cell's pressure. rho[k+1] is already that
        # cell at its own pressure; only the shallower cell must be re-evaluated
        # at the deeper reference pressure.
        pref_deep = pressure[1:nz]
        rho_shal_at_deep = (
            jmd95_eos(theta[:nz-1], salt[:nz-1], pref_deep, rho_const)[0] + rho_const
        )
        rho_deep = rho[1:nz]
        dbloc[:nz-1] = gravity * (rho_deep - rho_shal_at_deep) / rho_deep

        # dbsfc[k]: surface T/S evaluated at each deeper cell's pressure.
        rho_surf_at_k = (
            jmd95_eos(np.full(nz-1, theta[0]), np.full(nz-1, salt[0]),
                      pressure[1:nz], rho_const)[0] + rho_const
        )
        dbsfc[1:nz] = gravity * (rho[1:nz] - rho_surf_at_k) / rho[1:nz]
    else:
        # Linear EOS is pressure-independent, so a common reference pressure is
        # automatic; just apply the corrected sign and denominator.
        for k in range(nz - 1):
            dbloc[k] = gravity * (rho[k+1] - rho[k]) / rho[k+1]
        for k in range(1, nz):
            dbsfc[k] = gravity * (rho[k] - rho[0]) / rho[k]

    return rho_surf, dbloc, dbsfc, ttalpha, ssbeta


def compute_ggl90_buoyancy_frequency_squared(
    theta: np.ndarray,
    salt: np.ndarray,
    depth: np.ndarray,
    rho_const: float = 1029.0,
    gravity: float = 9.81,
    use_jmd95: bool = True,
    cell_thickness: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Compute N² for GGL90 using potential density gradients.

    This function exactly replicates MITgcm's GGL90 sigmaR calculation
    (grad_sigma.F + do_oceanic_phys.F), where the density gradient at
    interface k is computed as:

        sigmaR(k) = [ρ(T(k), S(k), P(k)) - ρ(T(k-1), S(k-1), P(k))] / Δz

    This is a POTENTIAL density gradient: the shallower cell's water (k-1)
    is evaluated at the deeper cell's pressure (k) before taking the
    difference. This removes compressibility effects and isolates the
    adiabatic (convective) density contrast.

    **MITgcm correspondence**:
        - grad_sigma.F:90-98 — sigmaR = (sigKp1 - sigKm1) * recip_drC
        - do_oceanic_phys.F:812-836 — sigKp1 = rho_insitu(k),
          sigKm1 = FIND_RHO_2D(T(k-1), S(k-1), P(k))
        - ggl90_calc.F:353-354 — Nsquare = gravity*gravitySign*recip_rhoConst*sigmaR

    **Bit-level operation order (1DMIX-068)**. MITgcm forms N² in exactly this
    order and this function reproduces it operation for operation, because
    floating-point addition/multiplication is not associative and in a
    near-neutral cell N² is itself only ~1 quantum of ρ (~2.3e-13 kg/m³) --
    a 1-ulp difference then moves the Richardson number ``Ri = N²/GGL90eps``
    across the 0.2 Prandtl-branch threshold:

        ρ' = FIND_RHO_2D(...)               density anomaly ρ - rhoConst (see ``jmd95_eos``:
                                            rhoP0 = rfresh + rsalt, bulk = bMfresh + bMsalt + bMpres)
        recip_drC = 1 / drC(k),  drC(k) = 0.5*(delR(k-1) + delR(k))
        sigmaR(k) = recip_drC * rkSign * (ρ'(k) - ρ'(k-1 @ P(k)))     rkSign = -1, left to right
        N²(k)     = gravity * gravitySign * recip_rhoConst * sigmaR(k) gravitySign = -1, recip_rhoConst = 1/rhoConst

    The centre-to-centre distance ``drC`` is built from the cell thicknesses
    when ``cell_thickness`` is given (MITgcm's ``ini_vertical_grid.F:123-127``);
    subtracting adjacent centre depths instead is a different rounding
    (e.g. -75.005 - -65 vs 0.5*(10 + 10.01)) and is only the fallback.

    Parameters
    ----------
    theta : np.ndarray, shape (nz,)
        Potential temperature profile [°C], cell centers
    salt : np.ndarray, shape (nz,)
        Salinity profile [psu], cell centers
    depth : np.ndarray, shape (nz,)
        Depth of cell centers (negative, increasing downward) [m]
    rho_const : float
        Reference density [kg/m^3]
    gravity : float
        Gravitational acceleration [m/s^2]
    use_jmd95 : bool
        If True, use JMD95 EOS; if False, use linear EOS
    cell_thickness : np.ndarray, shape (nz,), optional
        Layer thicknesses ``delR`` [m]. When given, ``drC(k) =
        0.5*(cell_thickness[k-1] + cell_thickness[k])`` as in MITgcm; when
        omitted, ``drC(k) = depth[k-1] - depth[k]`` (same value, different
        rounding -- exact only to ~1 ulp).

    Returns
    -------
    n_square : np.ndarray, shape (nz,)
        Buoyancy frequency squared [s⁻²], at cell interfaces.
        n_square[0] = 0 (surface), n_square[k] for k=1..nz-1 is the
        potential density gradient across interface k.

    Notes
    -----
    This differs from physics_basis.compute_buoyancy_frequency_squared,
    which operates on a pre-computed density array and cannot distinguish
    in-situ vs. potential density. This function performs the EOS calls
    needed to construct the potential density gradient.

    For KPP, use compute_buoyancy_gradients which returns dbloc/dbsfc
    with the KPP-specific scaling.
    """
    nz = len(theta)
    n_square = np.zeros(nz)

    # Pressure at each cell center, matching MITgcm's real EOS pressure
    # exactly -- see `_depth_to_eos_pressure` (1DMIX-039) rather than a flat
    # "1 dbar per metre".
    pressure = _depth_to_eos_pressure(depth, rho_const, gravity)
    # ... and the same pressure in bar formed in MITgcm's operation order
    # (bit-level; see `_mitgcm_eos_pressure_bar`, 1DMIX-068).
    p_bar = _mitgcm_eos_pressure_bar(depth, rho_const, gravity)

    # centre-to-centre distance drC(k), k = 1..nz-1 (index k-1 below)
    dr_c_depth = depth[:-1] - depth[1:]
    if cell_thickness is not None:
        dr_c = 0.5 * (cell_thickness[:-1] + cell_thickness[1:])
        # zero/invalid thickness (dry padding) cannot form a drC: fall back to
        # the centre-depth difference there instead of dividing by zero
        dr_c = np.where(dr_c > 0.0, dr_c, dr_c_depth)
    else:
        dr_c = dr_c_depth
    recip_dr_c = 1.0 / dr_c
    recip_rho_const = 1.0 / rho_const

    if use_jmd95:
        # sigKp1: density anomaly of level k at its own pressure P(k)
        rho_deep, _, _ = jmd95_eos(theta, salt, pressure, rho_const, pressure_bar=p_bar)

        # sigKm1: density anomaly of level k-1 water evaluated at P(k)
        # (potential density relative to the deeper interface). Vectorised:
        # every operation is elementwise IEEE, identical to a per-level loop.
        rho_shal_at_deep, _, _ = jmd95_eos(
            theta[:-1], salt[:-1], pressure[1:], rho_const, pressure_bar=p_bar[1:]
        )

        # MITgcm works on the density ANOMALIES rho - rhoConst (FIND_RHO_2D
        # returns rho - rhoConst) and subtracts them directly.
        # grad_sigma.F:93-95: recip_drC * rkSign * (sigKp1 - sigKm1)
        sigma_r = (recip_dr_c * -1.0) * (rho_deep[1:] - rho_shal_at_deep)

        # ggl90_calc.F:353-354, gravitySign = -1: g*gravitySign*recip_rhoConst*sigmaR
        n_square[1:] = ((gravity * -1.0) * recip_rho_const) * sigma_r

    else:
        # Linear EOS is pressure-independent, so potential = in-situ
        rho_anom, _, _ = linear_eos(theta, salt, -depth, rho_const)
        rho = rho_anom + rho_const

        for k in range(1, nz):
            dz = depth[k] - depth[k-1]
            drho_dz = (rho[k-1] - rho[k]) / dz
            n_square[k] = -(gravity / rho_const) * drho_dz

    return n_square
