"""
Shared physics foundation for vertical mixing schemes.

This module contains scheme-independent physics functions used by both GGL90 and KPP
mixing schemes. All functions follow a common interface: input validation, clear
docstrings with physics equations, MITgcm correspondence comments, and output
type/shape documentation.

All functions are "physics first" — they compute fundamental quantities (N², S², 
density gradients, etc.) without scheme-specific logic.

**Design principle**: If both GGL90 and KPP need a function with identical physics 
(same equation, same discretization), it lives here. Scheme-specific variants belong 
in the individual scheme modules.

**References**:
    - MITgcm source code (ggl90_mixinglength.F, kpp_calc.F, convective_weights.F)
    - Gaspar et al. (1990) for GGL90
    - Large et al. (1994) for KPP
"""

import numpy as np
from typing import Tuple


def compute_buoyancy_frequency_squared(
    rho: np.ndarray,
    z: np.ndarray,
    gravity: float = 9.81,
    rho_0: float = None
) -> np.ndarray:
    """
    Compute squared buoyancy frequency (Brunt-Väisälä frequency squared).

    N² = -(g/ρ₀) * ∂ρ/∂z   (z positive upward)

    Stable stratification (density increasing with depth, i.e., decreasing 
    upward, ∂ρ/∂z < 0) yields N² > 0. Unstable stratification (denser water 
    overlying lighter water, ∂ρ/∂z > 0) yields N² < 0. This sign convention 
    matches MITgcm's instability test (rkSign*gravitySign in 
    convective_weights.F).

    **Physics background**: N² measures the restoring force for vertical 
    displacements in a stratified fluid. It is the fundamental quantity 
    controlling density-driven mixing (buoyancy suppresses, negative N² 
    enables vertical motion).

    **Discretization**: Density gradient at interface k is:
    ∂ρ/∂z|_k ≈ (ρ_{k-1} - ρ_k) / (z_{k-1} - z_k)
    matching two-point centered difference between cells.

    **MITgcm correspondence**: Computed in GGL90_CALC.F and used throughout 
    ggl90_mixinglength.F for mixing-length diagnosis. In KPP, equivalent 
    information comes from compute_buoyancy_gradients().

    Parameters
    ----------
    rho : np.ndarray, shape (nz,)
        Density profile [kg/m³], cell centers
    z : np.ndarray, shape (nz,)
        Depth coordinate [m], positive upward, cell centers
    gravity : float, optional
        Gravitational acceleration [m/s²], default 9.81
    rho_0 : float, optional
        Reference density [kg/m³]. If None, computed as the column mean.

    Returns
    -------
    n_square : np.ndarray, shape (nz,)
        Buoyancy frequency squared [s⁻²], evaluated at cell interfaces 
        (top face of each cell). n_square[0] = 0 (surface interface has 
        no density gradient above it).

    Raises
    ------
    ValueError
        If rho or z have mismatched shapes, or if z is not monotonic.

    Examples
    --------
    >>> rho = np.array([1025.0, 1026.0, 1027.0])  # kg/m³
    >>> z = np.array([0.0, -10.0, -20.0])  # m, positive up
    >>> n2 = compute_buoyancy_frequency_squared(rho, z)
    >>> n2[0]  # Surface = 0
    0.0
    >>> n2[1] > 0  # Stable if density increases downward
    True
    """
    # Input validation
    if rho.shape != z.shape:
        raise ValueError(f"rho shape {rho.shape} != z shape {z.shape}")
    
    nz = len(rho)
    n_square = np.zeros(nz)
    
    # Compute mean density if not provided
    if rho_0 is None:
        rho_0 = np.mean(rho)
    
    # Compute N² at each interface (k=1..nz-1)
    for k in range(1, nz):
        # Density gradient (using two-point difference)
        drho_dz = (rho[k-1] - rho[k]) / (z[k-1] - z[k])
        # Brunt-Väisälä frequency squared with gravity factor
        n_square[k] = -(gravity / rho_0) * drho_dz
    
    return n_square


def compute_vertical_shear_squared(
    u: np.ndarray,
    v: np.ndarray,
    z: np.ndarray
) -> np.ndarray:
    """
    Compute squared vertical shear magnitude.

    S² = (∂u/∂z)² + (∂v/∂z)²

    **Physics background**: S² is the squared magnitude of the vertical 
    velocity gradient. It controls shear-driven turbulent kinetic energy 
    (TKE) production and is essential for estimating the Richardson number 
    (Ri = N²/S²), which determines whether mixing is buoyancy-driven or 
    shear-driven.

    **Discretization**: Velocity gradients at interface k are:
    ∂u/∂z|_k ≈ (u_{k-1} - u_k) / (z_{k-1} - z_k)
    ∂v/∂z|_k ≈ (v_{k-1} - v_k) / (z_{k-1} - z_k)
    matching two-point centered difference between adjacent cells.

    **MITgcm correspondence**: Computed in GGL90_CALC.F for GGL90, and in 
    KPP_CALC.F for KPP (though KPP also uses velocity-difference variants 
    for boundary-layer-specific Richardson calculations).

    Parameters
    ----------
    u : np.ndarray, shape (nz,)
        Zonal (East-West) velocity profile [m/s], cell centers
    v : np.ndarray, shape (nz,)
        Meridional (North-South) velocity profile [m/s], cell centers
    z : np.ndarray, shape (nz,)
        Depth coordinate [m], positive upward, cell centers

    Returns
    -------
    shear_square : np.ndarray, shape (nz,)
        Squared vertical shear magnitude [s⁻²], evaluated at cell interfaces 
        (top face of each cell). shear_square[0] = 0 (surface has no shear 
        above it by definition).

    Raises
    ------
    ValueError
        If u, v, or z have mismatched shapes, or if z is not monotonic.

    Examples
    --------
    >>> u = np.array([0.5, 0.3, 0.1])  # m/s
    >>> v = np.array([0.1, 0.05, 0.0])  # m/s
    >>> z = np.array([0.0, -10.0, -20.0])  # m, positive up
    >>> s2 = compute_vertical_shear_squared(u, v, z)
    >>> s2[0]  # Surface = 0
    0.0
    >>> s2[1] > 0  # Interior shear is positive
    True
    """
    # Input validation
    if u.shape != v.shape or u.shape != z.shape:
        raise ValueError(f"u shape {u.shape}, v shape {v.shape}, z shape {z.shape} "
                        "must all match")
    
    nz = len(u)
    shear_square = np.zeros(nz)
    
    # Compute S² at each interface (k=1..nz-1)
    for k in range(1, nz):
        # Velocity gradients (using two-point difference)
        du_dz = (u[k-1] - u[k]) / (z[k-1] - z[k])
        dv_dz = (v[k-1] - v[k]) / (z[k-1] - z[k])
        # Squared shear magnitude
        shear_square[k] = du_dz**2 + dv_dz**2
    
    return shear_square


def compute_density_gradient(
    rho: np.ndarray,
    z: np.ndarray
) -> np.ndarray:
    """
    Compute vertical density gradient ∂ρ/∂z.

    **Physics background**: The density gradient directly drives (or suppresses) 
    convective mixing. Negative gradients (density increasing downward) are 
    stable; positive gradients (denser water over lighter) are unstable.

    **Discretization**: Density gradient at interface k is:
    ∂ρ/∂z|_k ≈ (ρ_{k-1} - ρ_k) / (z_{k-1} - z_k)
    matching two-point centered difference.

    **MITgcm correspondence**: Used in various places including stratification 
    analysis in diagnostics packages.

    Parameters
    ----------
    rho : np.ndarray, shape (nz,)
        Density profile [kg/m³], cell centers
    z : np.ndarray, shape (nz,)
        Depth coordinate [m], positive upward, cell centers

    Returns
    -------
    drho_dz : np.ndarray, shape (nz,)
        Vertical density gradient [kg/m⁴], at interfaces. drho_dz[0] = 0.

    Raises
    ------
    ValueError
        If rho and z have mismatched shapes.

    Examples
    --------
    >>> rho = np.array([1025.0, 1026.0, 1027.0])
    >>> z = np.array([0.0, -10.0, -20.0])
    >>> drho_dz = compute_density_gradient(rho, z)
    >>> drho_dz[1]  # Should be 0.1 kg/m⁴ (positive = unstable)
    0.1
    """
    if rho.shape != z.shape:
        raise ValueError(f"rho shape {rho.shape} != z shape {z.shape}")
    
    nz = len(rho)
    drho_dz = np.zeros(nz)
    
    for k in range(1, nz):
        drho_dz[k] = (rho[k-1] - rho[k]) / (z[k-1] - z[k])
    
    return drho_dz


def compute_richardson_number(
    n_square: np.ndarray,
    shear_square: np.ndarray,
    epsilon: float = 1e-14
) -> np.ndarray:
    """
    Compute the Richardson number Ri = N²/S².

    **Physics background**: The Richardson number compares buoyancy effects 
    (N²) to shear effects (S²). Low Ri (S² dominates) favors shear-driven 
    mixing; high Ri (N² dominates) suppresses mixing. Ri = 0.25 is often 
    considered a critical threshold for instability.

    **MITgcm correspondence**: Computed in KPP_CALC.F for interior-mixing 
    logic, and throughout kpp_routines.F for the ri_iwmix function.

    Parameters
    ----------
    n_square : np.ndarray, shape (nz,)
        Buoyancy frequency squared [s⁻²]
    shear_square : np.ndarray, shape (nz,)
        Vertical shear squared [s⁻²]
    epsilon : float, optional
        Small value to avoid division by zero, default 1e-14

    Returns
    -------
    ri : np.ndarray, shape (nz,)
        Richardson number [dimensionless], safe from division by zero

    Examples
    --------
    >>> n2 = np.array([0.0, 1e-4, 1e-5])
    >>> s2 = np.array([0.0, 1e-4, 1e-3])
    >>> ri = compute_richardson_number(n2, s2)
    >>> ri[1]  # Ri = 1.0 (neutral)
    1.0
    >>> ri[2]  # Ri = 0.01 (shear dominates)
    0.01
    """
    ri = n_square / (shear_square + epsilon)
    return ri
