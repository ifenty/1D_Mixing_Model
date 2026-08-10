"""
Equation of state and buoyancy calculations.

Implements density, thermal expansion, and haline contraction computations.
Completely independent of mixing scheme - physical constants passed as parameters.
"""

import numpy as np
from typing import Tuple

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
        Depth (positive down) [m]
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

    # Convert pressure from dbar to bar
    p = 0.1 * p

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

    # Density of sea water at surface
    rho_surf = (rho_fresh
                + s * (eosJMDCSw[0]
                       + eosJMDCSw[1] * t
                       + eosJMDCSw[2] * t2
                       + eosJMDCSw[3] * t3
                       + eosJMDCSw[4] * t4)
                + s3o2 * (eosJMDCSw[5]
                          + eosJMDCSw[6] * t
                          + eosJMDCSw[7] * t2)
                + eosJMDCSw[8] * s * s)

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

    # Chain rule for in-situ density derivative
    ttalpha = drho_dt_surf / (1.0 - p / bulkmod) + rho_surf * p * dbulkmod_dt / (bulkmod * (bulkmod - p))

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

    # Chain rule for in-situ density derivative
    ssbeta = drho_ds_surf / (1.0 - p / bulkmod) + rho_surf * p * dbulkmod_ds / (bulkmod * (bulkmod - p))

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

    # Bulk modulus of sea water at surface
    bulkmod_surf = (bulkmod_fresh
                    + s * (eosJMDCKSw[0]
                           + eosJMDCKSw[1] * t
                           + eosJMDCKSw[2] * t2
                           + eosJMDCKSw[3] * t3)
                    + s3o2 * (eosJMDCKSw[4]
                              + eosJMDCKSw[5] * t
                              + eosJMDCKSw[6] * t2))

    # Bulk modulus at pressure p
    bulkmod = (bulkmod_surf
               + p * (eosJMDCKP[0]
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
) -> np.ndarray:
    """
    Flag statically unstable interfaces (denser water directly overlying
    lighter water), for a scheme-independent convective-adjustment step
    (MITgcm's `ivdc_kappa`, see calc_ivdc.F / convective_weights.F).

    MITgcm's own instability test only depends on the SIGN of the density
    gradient (`-sigmaR*gravitySign > 0`), not on any particular scaling of
    N^2, so this only needs in-situ density -- no gravity/rho0 scaling.

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

    Returns
    -------
    unstable : np.ndarray of bool, shape (nz,)
        True at interface k (top face of cell k, between cells k-1 and k)
        where cell k-1 (shallower) is denser than cell k (deeper). Index 0
        (surface face) is always False.
    """
    pressure = -depth  # dbar, ~1 dbar per meter (depth is negative-down)
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

    # Pressure at each cell centre. Hydrostatically, 1 dbar of pressure
    # corresponds to ~1 m of seawater, so pressure in dbar ~ depth in metres.
    # `depth` is negative-down, so pressure = -depth.
    #
    # NOTE (bug fix): the previous port used `-depth / 10.0`, which is a
    # factor of 10 too small (it would put 1000 m at only 100 dbar). That
    # under-stated the compressibility correction in the EOS. The correct
    # dbar~m relationship is restored here. This matches the pressure that
    # MITgcm's PRESSURE_FOR_EOS supplies to FIND_RHO_2D (hydrostatic pressure
    # ~ rho*g*depth, i.e. ~depth in dbar for seawater).
    pressure = -depth  # dbar

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
        - ggl90_calc.F:347-348 — Nsquare = g * sigmaR / rho_const

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

    # Pressure at each cell center (dbar ~ depth in meters)
    pressure = -depth

    if use_jmd95:
        # Compute in-situ density at all levels
        rho_anom, _, _ = jmd95_eos(theta, salt, pressure, rho_const)
        rho_insitu = rho_anom + rho_const

        # For each interface k (between cells k-1 and k):
        # sigmaR(k) = [rho_insitu(k) - rho_potential(k-1 at pressure k)] / dz
        for k in range(1, nz):
            # rho_deep: in-situ density at level k
            rho_deep = rho_insitu[k]

            # rho_shal_at_deep: potential density of level k-1 water
            # evaluated at level k's pressure
            rho_shal_anom, _, _ = jmd95_eos(
                np.array([theta[k-1]]),
                np.array([salt[k-1]]),
                np.array([pressure[k]]),
                rho_const
            )
            rho_shal_at_deep = rho_shal_anom[0] + rho_const

            # Density gradient: ∂ρ/∂z where z is positive up
            # depth is negative-down, so z = -depth (positive-up)
            # z[k-1] > z[k] (shallower is less negative)
            # For stable: rho[k-1] < rho[k] (lighter above denser)
            # drho/dz = (rho[k] - rho[k-1]) / (z[k] - z[k-1]) < 0
            dz = depth[k] - depth[k-1]  # negative (depth[k] is more negative)
            drho_dz = (rho_deep - rho_shal_at_deep) / dz  # Corrected: deep - shallow

            # N² = -(g/ρ₀) × ∂ρ/∂z
            # For stable stratification: drho/dz < 0, so N² > 0
            n_square[k] = -(gravity / rho_const) * drho_dz

    else:
        # Linear EOS is pressure-independent, so potential = in-situ
        rho_anom, _, _ = linear_eos(theta, salt, -depth, rho_const)
        rho = rho_anom + rho_const

        for k in range(1, nz):
            dz = depth[k] - depth[k-1]
            drho_dz = (rho[k-1] - rho[k]) / dz
            n_square[k] = -(gravity / rho_const) * drho_dz

    return n_square
