"""
Shared implicit vertical-diffusion solver for the 1D column models.

Both KPP_PY and GGL90_PY advance tracers/velocities through time by solving the
same 1D vertical diffusion equation

    d C / d t = d/dz ( K dC/dz )  (+ surface flux BC, + optional KPP nonlocal term)

with a backward-Euler (fully implicit) time discretization. Backward Euler is
UNCONDITIONALLY STABLE for diffusion, so it does not suffer the explicit-scheme
CFL limit dt < dz^2 / (2 K) that made the old example_usage.py stepper blow up
(negative salinity -> sqrt NaN) on thin near-surface cells.

This module is the SINGLE SOURCE OF TRUTH for that time-stepping method: every
model (KPP_PY/example_usage.py, KPP_PY/extreme_scenarios.py,
GGL90_PY/example_1d_column.py) calls solve_diffusion_implicit() here, so all of
them use bit-for-bit the same solver.

Vertical staggering (MITgcm-faithful "top-of-cell" interface convention):
  * Cell-centered fields C of length nz. depth[0] is the surface-most cell.
  * `depth` : cell-center depths, negative-downward (depth[0] nearest surface),
    length nz. Center-to-center spacing across the TOP face of cell k is
    drC[k] = depth[k-1] - depth[k] > 0 (defined for k=1..nz-1).
  * `thickness` : cell thicknesses [m] (drF), length nz, all > 0.
  * `k_interface[k]` : diffusivity at the TOP FACE of cell k -- the interface
    between cell k-1 (above) and cell k (below). Index k=0 is the ocean SURFACE
    face, where k_interface[0] = 0 (no diffusive flux through the surface). This
    is EXACTLY MITgcm's KPPdiffKzT/S/viscAz and GGL90viscAz/diffKr layout:
    array index k lives at rF(k) = top of cell k, with the k=1 (Fortran) /
    k=0 (Python) surface entry zero. Both KPP and GGL90 produce their kappa on
    this convention natively, so no face-averaging/interpolation is applied here.
  * `surface_flux` : kinematic surface flux of C (Q/(rho*cp) for heat, tau/rho
    for momentum, -(E-P)*S for salt), positive = added to the column. Applied as
    a Neumann BC on the surface face; the bottom face is no-flux.
  * `ghat` (optional) : KPP nonlocal transport coefficient [s/m^2], length nz.
    MITgcm stores ghat at the BOTTOM face of cell k (kpp_transport_t.F:21-25),
    i.e. half a level offset from diffKz, so the flux through the top face of
    cell k pairs k_interface[k] with ghat[k-1] (kpp_transport_t.F:92-93):
    nonlocal flux across top face of cell k = k_interface[k]*ghat[k-1]*surface_flux
    (LMD94's -K(dC/dz - ghat*F0)). GGL90 does not use this and passes ghat=None.
"""

from __future__ import annotations

import numpy as np


def solve_tridiagonal(a, b, c, d):
    """Solve a tridiagonal system A x = d (Thomas algorithm).

    a : sub-diagonal   (a[0] unused)
    b : main diagonal
    c : super-diagonal (c[-1] unused)
    d : right-hand side

    This is the one canonical tridiagonal solve used by every column model.
    """
    n = len(d)
    cp = np.zeros(n)
    dp = np.zeros(n)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for k in range(1, n):
        denom = b[k] - a[k] * cp[k - 1]
        cp[k] = c[k] / denom
        dp[k] = (d[k] - a[k] * dp[k - 1]) / denom
    x = np.zeros(n)
    x[-1] = dp[-1]
    for k in range(n - 2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k + 1]
    return x


def solve_diffusion_implicit(c_old, k_interface, depth, thickness, dt,
                             surface_flux=0.0, ghat=None):
    """One backward-Euler implicit vertical-diffusion step.

    Neumann (flux) surface BC, no-flux bottom BC, optional KPP nonlocal term.
    Uses the MITgcm top-of-cell interface convention (see module docstring):
    k_interface[k] is the diffusivity at the TOP face of cell k, coupling cells
    k-1 and k; k_interface[0] (surface face) is unused (no surface diffusive
    flux). Returns the updated field (length nz). Unconditionally stable in dt.
    """
    c_old = np.asarray(c_old, dtype=float)
    k_interface = np.asarray(k_interface, dtype=float)
    depth = np.asarray(depth, dtype=float)
    thickness = np.asarray(thickness, dtype=float)

    nz = len(c_old)
    if nz == 1:
        # Degenerate single-cell column: only the surface flux acts.
        return c_old + dt * surface_flux / thickness[0]

    # Coupling across the TOP face of cell k (interface between cells k-1 and k),
    # for k = 1..nz-1. drC[k] = depth[k-1] - depth[k] > 0 (center-to-center).
    # cond_top[k] = k_interface[k] / drC[k]. cond_top[0] (surface face) is 0.
    drC = depth[:-1] - depth[1:]             # len nz-1: drC_full[j] spans cells j,j+1
    cond_top = np.zeros(nz)
    cond_top[1:] = k_interface[1:] / drC     # top face of cell k uses drC[k-1..]=depth[k-1]-depth[k]

    # Nonlocal flux through the top face of cell k pairs k_interface[k] with
    # ghat[k-1] (MITgcm's half-level ghat offset). nl_top[k], k=1..nz-1.
    nl_top = np.zeros(nz)
    if ghat is not None and surface_flux != 0.0:
        ghat = np.asarray(ghat, dtype=float)
        nl_top[1:] = k_interface[1:] * ghat[: nz - 1] * surface_flux

    a = np.zeros(nz)
    b = np.zeros(nz)
    c = np.zeros(nz)
    d = np.zeros(nz)

    for k in range(nz):
        d[k] = thickness[k] / dt * c_old[k]
        # Diffusive coupling: top face of cell k (cond_top[k], to cell k-1) and
        # top face of cell k+1 (cond_top[k+1], to cell k+1). cond_top[0]=0 gives
        # the surface no-flux face; cond_top[nz] does not exist (bottom no-flux).
        cond_up = cond_top[k]                    # top face of cell k (0 at surface)
        cond_dn = cond_top[k + 1] if k < nz - 1 else 0.0
        a[k] = -cond_up
        c[k] = -cond_dn
        b[k] = thickness[k] / dt + cond_up + cond_dn
        # Surface kinematic flux enters the top cell.
        if k == 0:
            d[k] += surface_flux
        # Nonlocal transport: flux in through top face of cell k, out through
        # top face of cell k+1.
        d[k] += nl_top[k] - (nl_top[k + 1] if k < nz - 1 else 0.0)

    return solve_tridiagonal(a, b, c, d)
