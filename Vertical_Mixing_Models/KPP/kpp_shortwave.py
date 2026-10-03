"""
Shortwave radiation penetration (Paulson & Simpson 1977 double-exponential),
matching MITgcm's SWFRAC.F used by KPP when SHORTWAVE_HEATING /
selectPenetratingSW is active.

swfrac(z) is the fraction of shortwave radiation that has NOT yet been
absorbed at depth z (positive, meters below surface): swfrac(0) = 1.

Water type (1DMIX-080): MITgcm hard-codes Jerlov type IA -- `jwtype=2` in
model/src/swfrac.F (lines 92 and 94, both branches of `#ifdef ALLOW_CAL`;
header line 23 "Parameter jwtype is hardcoded to 2 for time being"). No
namelist parameter sets it, so no MITgcm capture records it; the port's
default is therefore "IA" here and in `KPPParameters.jerlov_water_type`.

200 m cut-off (1DMIX-085): swfrac.F:98-100 sets the fraction to exactly 0
when `facz .LT. -200.` (`facz = fact*swdk`, the negative distance from the
surface), i.e. strictly deeper than 200 m; at exactly 200 m the double
exponential is kept. `swfrac` applies the same test to `facz = -depth_m`, so
every caller (the three bldepth call sites in `kpp_scheme_specific.py::
diagnose_bl_depth`, MITgcm kpp_routines.F:508/703/839) gets it.
"""

import numpy as np

# R, D1 [m], D2 [m] per Jerlov water type (Paulson & Simpson, 1977); equal, digit
# for digit, to swfrac.F's `DATA rfac / a1 / a2` (lines 71-76; jwtype 1..5 = I, IA, IB, II, III).
JERLOV_TABLE = {
    "I":   (0.58, 0.35, 23.0),
    "IA":  (0.62, 0.60, 20.0),
    "IB":  (0.67, 1.00, 17.0),
    "II":  (0.77, 1.50, 14.0),
    "III": (0.78, 1.40, 7.9),
}


def swfrac(depth_m, water_type: str = "IA"):
    """
    Fraction of shortwave irradiance remaining at depth `depth_m` (>= 0).

    MITgcm swfrac.F:97-105: `facz = fact*swdk` (here `facz = -depth_m`, the
    negative distance from the surface); exactly 0 if `facz < -200` (lines
    99-100, strict: depth > 200 m; 1DMIX-085), else
    `rfac*exp(facz/a1) + (1-rfac)*exp(facz/a2)` (lines 102-103) with identical
    operation order, bit-identical to MITgcm's own SWFRAC output for type IA
    (1DMIX-080; captured `swatt`, including its exact zeros below 200 m).

    Parameters
    ----------
    depth_m : array_like
        Positive depth(s) below the surface [m].
    water_type : str
        One of JERLOV_TABLE keys ("I", "IA", "IB", "II", "III"). Default "IA",
        MITgcm's hard-coded type (swfrac.F line 92/94, `jwtype=2`).

    Returns
    -------
    np.ndarray
        Fraction of shortwave still present at depth (1 at surface, decreasing
        with depth, exactly 0 below 200 m).
    """
    if water_type not in JERLOV_TABLE:
        raise ValueError(
            f"Unknown Jerlov water type '{water_type}', choose from {list(JERLOV_TABLE)}"
        )
    r, d1, d2 = JERLOV_TABLE[water_type]
    z = np.atleast_1d(np.asarray(depth_m, dtype=float))
    frac = r * np.exp(-z / d1) + (1.0 - r) * np.exp(-z / d2)
    # swfrac.F:99-100, `IF ( facz .LT. -200. _d 0 ) swdk(i) = 0. _d 0` with facz = -depth_m (1DMIX-085).
    frac = np.where(-z < -200.0, 0.0, frac)
    return frac
