"""
Tracer-point velocity-derived inputs for the MITgcm-capture replays (1DMIX-071).

MITgcm forms the shear a mixing scheme sees at a TRACER point (i, j) from the velocities on
the surrounding U/V faces: uVel at (i, i+1), vVel at (j, j+1) and, for KPP's horizontally
smoothed quantities, the 3x3 neighbourhood. The captures hold `uVel(i, j)` and `vVel(i, j)`
for every wet tile-interior column of the whole (global) grid, so the neighbours of every
column are other columns of the same capture, and this module rebuilds exactly what MITgcm
used. Arrays have shape (time, x, y, z) with x, y the global index.

Line numbers cited below are those of the instrumented copies the captures were built from
(`mitgcm_verification_mods/kpp_mods/kpp_calc.F`, `kpp_routines.F`, `ggl90_mods/ggl90_calc.F`;
the physics equals stock pkg/kpp and pkg/ggl90, only output code is added) and of stock
`pkg/kpp/kpp_forcing_surf.F` (not instrumented).

Neighbour rule (`periodic_x`, `periodic_y`, both default True): MITgcm's halo exchange is
periodic in both directions unless `notUsingXPeriodicity`/`notUsingYPeriodicity` is set (none
of the declared experiments' eedata sets it; closed basins are closed by land columns of the
bathymetry, which carry velocity 0). A neighbour beyond a non-periodic edge reads 0. No capture
records its periodicity. Where the periodic-wrap rule is actually verified (wrap and zero-fill give
different reconstructions and wrap matches the capture; counts from this issue and from Richard's
review): x on `global_ocean.90x40x15` (GGL90 2,790 of 3,830 domain-edge interfaces; KPP 6,039 of
10,220), `global_oce_latlon` (1,610 cells, review) and `seaice_obcs` (245); y only on `seaice_obcs`
and the 1x1 single-column captures. NOT verified: y on the global grids and on every GGL90 capture,
and both axes on `lab_sea` and `isomip`, because wrap and zero-fill give identical reconstructions
there (closed basins whose edge columns are land).

The wrap rule is validated against the captured `vertical_shear`,
`shear_sq` and `dVsq` (zero relative difference for KPP; <1e-15 for GGL90) in
`tests/test_tracer_point_inputs.py`, which would fail for a capture of a different edge behaviour added to its list.

GGL90 (`tracer_point_velocities`): ggl90_calc.F:541-556 (calcMeanVertShear=.FALSE.) computes
`((u(i,k-1)+u(i+1,k-1)) - (u(i,k)+u(i+1,k)))*halfRL*recip_drC(k)` (and v with j, j+1) and squares
and adds them, i.e. the squared vertical shear of ubar=(u(i)+u(i+1))/2, vbar=(v(j)+v(j+1))/2. Feeding
ubar/vbar to the port (`compute_vertical_shear_squared`) is therefore exact; no driver change.
The calcMeanVertShear=.TRUE. branch (526-540, a sum of squares of four separate differences) is NOT
reproducible this way (1DMIX-074 tracks the port ignoring that flag).

KPP: shsq, dVsq (and the smoothed dbloc) are means of squared differences, not functions of
an averaged velocity, so they are supplied to `KPPDriver.compute_mixing` through its keyword-only
`shsq_forcing`, `dvsq_forcing`, `dbloc_smooth_forcing`. The functions below transcribe, in the
same operation order, kpp_calc.F:459-495 (`kpp_shsq`), kpp_forcing_surf.F:463-504 (`kpp_dvsq`)
and kpp_routines.F:1318-1398 (`smooth_horiz`, applied as kpp_calc.F:276-289 does).
Options this module does not implement are refused with NotImplementedError
(`check_supported_kpp_options`): KPP_ESTIMATE_UREF, KPP_SMOOTH_DVSQ, KPP_SMOOTH_DENS,
KPP_SMOOTH_VISC, KPP_SMOOTH_DIFF.
"""

from typing import Mapping, Tuple

import numpy as np


# --------------------------------------------------------------------------- neighbours

def neighbour(a: np.ndarray, di: int, dj: int, periodic_x: bool = True,
              periodic_y: bool = True) -> np.ndarray:
    """b[:, i, j] = a[:, i+di, j+dj]; wraps if periodic, else reads 0 beyond the edge.

    `a` has shape (time, x, y, ...); the global index lives on axes 1 and 2."""
    out = a
    for axis, d, periodic in ((1, di, periodic_x), (2, dj, periodic_y)):
        if d == 0:
            continue
        if periodic:
            out = np.roll(out, -d, axis=axis)
        else:
            shifted = np.zeros_like(out)
            n = out.shape[axis]
            src = [slice(None)] * out.ndim
            dst = [slice(None)] * out.ndim
            if d > 0:
                src[axis], dst[axis] = slice(d, n), slice(0, n - d)
            else:
                src[axis], dst[axis] = slice(0, n + d), slice(-d, n)
            shifted[tuple(dst)] = out[tuple(src)]
            out = shifted
    return out


# --------------------------------------------------------------------------- GGL90

def tracer_point_velocities(u: np.ndarray, v: np.ndarray, periodic_x: bool = True,
                            periodic_y: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """ubar=(u(i)+u(i+1))/2, vbar=(v(j)+v(j+1))/2 (ggl90_calc.F:545-552)."""
    ubar = 0.5 * (u + neighbour(u, 1, 0, periodic_x, periodic_y))
    vbar = 0.5 * (v + neighbour(v, 0, 1, periodic_x, periodic_y))
    return ubar, vbar


# --------------------------------------------------------------------------- KPP

_UNSUPPORTED_KPP_OPTIONS = {
    'estimate_uref': 'KPP_ESTIMATE_UREF (kpp_forcing_surf.F:309-461)',
    'smooth_dvsq': 'KPP_SMOOTH_DVSQ (kpp_forcing_surf.F:481-499)',
    'smooth_dens': 'KPP_SMOOTH_DENS (kpp_calc.F:291-315)',
    'smooth_visc': 'KPP_SMOOTH_VISC (kpp_calc.F:618-628)',
    'smooth_diff': 'KPP_SMOOTH_DIFF (kpp_calc.F:630-642)',
}


def check_supported_kpp_options(attrs: Mapping) -> None:
    """Raise NotImplementedError if the capture was built with an option whose
    multi-column effect this module does not reproduce."""
    flagged = [desc for key, desc in _UNSUPPORTED_KPP_OPTIONS.items()
               if int(attrs.get(key, 0)) != 0]
    if flagged:
        raise NotImplementedError(
            "tracer-point KPP inputs are not implemented for: " + "; ".join(flagged)
            + ". Replay with tracer_point_inputs=False (column-local) instead.")


def _sq(a):
    return a * a


def kpp_shsq(u: np.ndarray, v: np.ndarray, smooth: bool, periodic_x: bool = True,
             periodic_y: bool = True) -> np.ndarray:
    """MITgcm shsq(i,j,k), k = 1..Nr (kpp_calc.F:459-498), shape (t, x, y, nz); shsq(Nr)=0.

    kpp_calc.F:468-476:  p5*[ (u(i,k)-u(i,k+1))^2 + (u(i+1,k)-u(i+1,k+1))^2
                              + (v(j,k)-v(j,k+1))^2 + (v(j+1,k)-v(j+1,k+1))^2 ]
    with KPP_SMOOTH_SHSQ (kpp_calc.F:477-495): p5*shsq + p125*(8 further squared differences:
    u at (i,j-1),(i+1,j-1),(i,j+1),(i+1,j+1) and v at (i-1,j),(i-1,j+1),(i+1,j),(i+1,j+1)).
    The additions follow the Fortran left-to-right order, so the result equals the captured
    `shear_sq` bit for bit."""
    nb = lambda a, di, dj: neighbour(a, di, dj, periodic_x, periodic_y)
    du = u[..., :-1] - u[..., 1:]
    dv = v[..., :-1] - v[..., 1:]
    core = 0.5 * (_sq(du) + _sq(nb(du, 1, 0)) + _sq(dv) + _sq(nb(dv, 0, 1)))
    if smooth:
        ring = (_sq(nb(du, 0, -1)) + _sq(nb(du, 1, -1)) + _sq(nb(du, 0, 1)) + _sq(nb(du, 1, 1))
                + _sq(nb(dv, -1, 0)) + _sq(nb(dv, -1, 1)) + _sq(nb(dv, 1, 0)) + _sq(nb(dv, 1, 1)))
        core = 0.5 * core + 0.125 * ring
    return np.concatenate([core, np.zeros_like(core[..., :1])], axis=-1)


def kpp_dvsq(u: np.ndarray, v: np.ndarray, periodic_x: bool = True,
             periodic_y: bool = True) -> np.ndarray:
    """MITgcm dVsq(i,j,k) with KPP_ESTIMATE_UREF and KPP_SMOOTH_DVSQ both undefined
    (kpp_forcing_surf.F:463-480): p5*[ (u(i,1)-u(i,k))^2 + (u(i+1,1)-u(i+1,k))^2
    + (v(j,1)-v(j,k))^2 + (v(j+1,1)-v(j+1,k))^2 ], shape (t, x, y, nz)."""
    nb = lambda a, di, dj: neighbour(a, di, dj, periodic_x, periodic_y)
    du = u[..., :1] - u
    dv = v[..., :1] - v
    return 0.5 * (_sq(du) + _sq(nb(du, 1, 0)) + _sq(dv) + _sq(nb(dv, 0, 1)))


def smooth_horiz(fld: np.ndarray, wet: np.ndarray, periodic_x: bool = True,
                 periodic_y: bool = True) -> np.ndarray:
    """Transcription of MITgcm `smooth_horiz` (kpp_routines.F:1318-1398) for one level at a time,
    vectorised over (t, x, y, level): `fld[..., n]` is smoothed with the mask `wet[..., n]` (the
    caller passes the level's maskC, i.e. level k+1 for dbloc(k), see kpp_calc.F:282-287).

      tempVar = p25*mask(i,j) + p125*(mask(i-1,j)+mask(i+1,j)+mask(i,j-1)+mask(i,j+1))
              + p0625*(mask(i-1,j-1)+mask(i-1,j+1)+mask(i+1,j-1)+mask(i+1,j+1))   [1360-1369]
      if tempVar >= p25:  fld_new = ( p25*fld*mask + p125*(four edge neighbours, each * its mask)
              + p0625*(four corner neighbours, each * its mask) ) / tempVar                [1370-1381]
      else:               fld_new = fld                                                    [1382-1383]
    """
    nb = lambda a, di, dj: neighbour(a, di, dj, periodic_x, periodic_y)
    m = wet.astype(np.float64)
    f = fld
    temp = (0.25 * m
            + 0.125 * (nb(m, -1, 0) + nb(m, 1, 0) + nb(m, 0, -1) + nb(m, 0, 1))
            + 0.0625 * (nb(m, -1, -1) + nb(m, -1, 1) + nb(m, 1, -1) + nb(m, 1, 1)))
    num = (0.25 * f * m
           + 0.125 * (nb(f, -1, 0) * nb(m, -1, 0) + nb(f, 1, 0) * nb(m, 1, 0)
                      + nb(f, 0, -1) * nb(m, 0, -1) + nb(f, 0, 1) * nb(m, 0, 1))
           + 0.0625 * (nb(f, -1, -1) * nb(m, -1, -1) + nb(f, -1, 1) * nb(m, -1, 1)
                       + nb(f, 1, -1) * nb(m, 1, -1) + nb(f, 1, 1) * nb(m, 1, 1)))
    return np.where(temp >= 0.25, num / np.where(temp > 0.0, temp, 1.0), f)


def kpp_dbloc_smooth(dbloc: np.ndarray, wet: np.ndarray, periodic_x: bool = True,
                     periodic_y: bool = True) -> np.ndarray:
    """Horizontally smoothed dbloc (the `ghat` argument of KPPMIX; kpp_calc.F:276-289).

    `dbloc[..., k]` is the raw buoyancy difference between levels k and k+1 of each captured
    column (zero where the column is dry), `wet` the (t, x, y, nz) wet mask (theta != 0).
    Levels k = 1..Nr-1 are smoothed with maskC(k+1) (the loop `DO k = 1, Nr-1 ... SMOOTH_HORIZ(k+1,
    ghat(k))`); the last level is left raw. Where level k or k+1 is dry the value is returned
    unsmoothed (MITgcm multiplies by maskC(k)*maskC(k+1) afterwards, kpp_calc.F:330-333, and the
    driver ignores those interfaces)."""
    out = dbloc.copy()
    sm = smooth_horiz(dbloc[..., :-1], wet[..., 1:], periodic_x, periodic_y)
    use = wet[..., :-1] & wet[..., 1:]
    out[..., :-1] = np.where(use, sm, dbloc[..., :-1])
    return out
