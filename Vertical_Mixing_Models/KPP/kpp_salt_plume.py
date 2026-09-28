"""
Salt-plume penetration fraction (Duffy et al. 1999), matching MITgcm's
SALT_PLUME_FRAC used by KPP's bldepth when useSALT_PLUME is active.

plume_frac(z, fact, sp_depth) returns the fraction of the surface
salt-plume haline buoyancy forcing (boplume) that has already been
distributed by depth `fact*z`. Unlike kpp_shortwave.py::swfrac (which
returns the fraction of shortwave NOT yet absorbed, i.e. remaining),
SALT_PLUME_FRAC reports the complementary, already-cumulative quantity
directly -- see its own docstring: "if surface value is Saltplume0, and
each level gets equal fraction 1/5 down to SPDepth=5, ... plumek =
1/5,2/5,3/5,4/5,5/5 on output". So this is the salt-plume analogue of
`1 - swfrac(z)`, not of `swfrac(z)` itself.

Only PlumeMethod=1 (uniform/power distribution) with Npower=0 (the
MITgcm default, and the only variant confirmed used by every
salt-plume-active experiment this project has captured -- see
seaice_obcs's own data.salt_plume) is implemented here.
KPPParameters.__post_init__ raises NotImplementedError for any other
PlumeMethod/Npower/SALT_PLUME_VOLUME configuration rather than silently
mishandling it.

Reference: Duffy, P. B., Bitz, C. M., & Marshall, J. C. (1999),
GRL, salt plume parameterization for sea-ice brine rejection.
Translated from MITgcm pkg/salt_plume/salt_plume_frac.F (PlumeMethod=1,
Npower=0 branch, lines 93-107).
"""

import numpy as np


def plume_frac(z, fact: float, sp_depth):
    """
    Fraction of the salt-plume buoyancy forcing distributed by depth `z`.

    Mirrors SALT_PLUME_FRAC's PlumeMethod=1/Npower=0 branch exactly
    (salt_plume_frac.F:93-107):

        facz = abs(fact*z)
        IF (SPDepth >= facz .AND. SPDepth > 0) THEN
            plumek = max(0, facz/SPDepth)          ! Npower=0: S**1
        ELSE
            plumek = 1                             ! past the plume depth,
                                                     ! or plume inactive here
        ENDIF

    Parameters
    ----------
    z : array_like
        Depth argument; `fact*z` is the negative distance from the
        surface [m], exactly matching SALT_PLUME_FRAC's own `plumek`
        input convention (salt_plume_frac.F:58-60). MITgcm's two call
        sites in bldepth use this with different (z, fact) pairs:
        `z=zgrid(kl)` (negative) with `fact=hbf` inside the candidate-
        boundary-layer search loop (kpp_routines.F:534-539), and
        `z=hbl` (positive) with `fact=-1` for the pre-/post-limit
        evaluations at the trial/final hbl (kpp_routines.F:730-734,
        867-871) -- the same two (depth, fact) conventions already used
        by the existing swfrac calls in diagnose_bl_depth.
    fact : float
        Scale factor applied to `z` before taking the absolute value
        (SALT_PLUME_FRAC's own `fact` argument).
    sp_depth : array_like
        Salt plume penetration (e-folding) depth [m] (SPDepth), >= 0.

    Returns
    -------
    np.ndarray
        Fraction of boplume already distributed by this depth, in [0, 1].
    """
    facz = np.abs(fact * np.atleast_1d(np.asarray(z, dtype=float)))
    sp_depth = np.atleast_1d(np.asarray(sp_depth, dtype=float))
    active = (sp_depth >= facz) & (sp_depth > 0.0)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(sp_depth > 0.0, facz / sp_depth, 0.0)
    return np.where(active, np.maximum(0.0, ratio), 1.0)
