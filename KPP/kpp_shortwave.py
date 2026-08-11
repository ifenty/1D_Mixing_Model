"""
Shortwave radiation penetration (Paulson & Simpson 1977 double-exponential),
matching MITgcm's SWFRAC.F used by KPP when SHORTWAVE_HEATING /
selectPenetratingSW is active.

swfrac(z) is the fraction of shortwave radiation that has NOT yet been
absorbed at depth z (positive, meters below surface): swfrac(0) = 1.
"""

import numpy as np

# R, D1 [m], D2 [m] per Jerlov water type (Paulson & Simpson, 1977).
JERLOV_TABLE = {
    "I":   (0.58, 0.35, 23.0),
    "IA":  (0.62, 0.60, 20.0),
    "IB":  (0.67, 1.00, 17.0),
    "II":  (0.77, 1.50, 14.0),
    "III": (0.78, 1.40, 7.9),
}


def swfrac(depth_m, water_type: str = "IB"):
    """
    Fraction of shortwave irradiance remaining at depth `depth_m` (>= 0).

    Parameters
    ----------
    depth_m : array_like
        Positive depth(s) below the surface [m].
    water_type : str
        One of JERLOV_TABLE keys ("I", "IA", "IB", "II", "III").

    Returns
    -------
    np.ndarray
        Fraction of shortwave still present at depth (1 at surface, -> 0 with depth).
    """
    if water_type not in JERLOV_TABLE:
        raise ValueError(
            f"Unknown Jerlov water type '{water_type}', choose from {list(JERLOV_TABLE)}"
        )
    r, d1, d2 = JERLOV_TABLE[water_type]
    z = np.atleast_1d(np.asarray(depth_m, dtype=float))
    frac = r * np.exp(-z / d1) + (1.0 - r) * np.exp(-z / d2)
    return frac
