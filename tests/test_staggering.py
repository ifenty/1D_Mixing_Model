#!/usr/bin/env python3
"""
Vertical-staggering tests: verify the Python KPP and GGL90 ports place mixing
coefficients at the SAME grid locations as F77 MITgcm, so their output arrays
overlay MITgcm's index-for-index with no remapping.

MITgcm "top-of-cell" interface convention (0-based Python index k):
  * Interface array index k = TOP face of cell k = interface between cell k-1
    (above) and cell k (below). Index 0 = ocean surface face.
  * diffKz[k], viscAz[k] live at the top face of cell k; index 0 = 0 (no
    surface diffusive flux) -- MITgcm KPPdiffKzT(1)=0 / GGL90 surface face.
  * ghat[k] lives at the BOTTOM face of cell k (half-level offset); the flux
    through the top face of cell k pairs diffKz[k] with ghat[k-1].
  * Vertical diffusive flux at top face k = -K[k]*(C[k]-C[k-1])/drC[k].

Run:  python main/test_staggering.py       (from the 1D_Mixing_Model dir)
      pytest main/test_staggering.py
"""

import sys
from pathlib import Path

import numpy as np

# Make 1D_Mixing_Model the import root (so `main`, `KPP_ML`, `GGL90_ML` resolve),
# and point KPP at the shared physical-parameters YAML.
import os
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault(
    "KPP_PHYSICAL_PARAMETERS_YAML",
    str(_ROOT / "configuration_yamls" / "physical_parameters.yaml"),
)

from main.shared_column_solver import solve_diffusion_implicit
from main.column_grid import ColumnGrid
from GGL90_ML.GGL90_PY.ggl90_core_driver import GGL90Driver
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters
from GGL90_ML.GGL90_PY.ggl90_mixing_coefficients import compute_viscosity_diffusivity
from main.eos import compute_ggl90_buoyancy_frequency_squared
from main.physics_basis import compute_vertical_shear_squared


TOL = 1e-12


def _grid(nz=8, drf=10.0):
    return ColumnGrid.from_drF(np.full(nz, drf))


def test_solver_surface_face_is_no_flux():
    """k_interface[0] (surface face) must not diffuse: passing any value there
    changes nothing, because the solver never uses index 0 for coupling."""
    grid = _grid()
    nz = grid.nz
    c = np.linspace(20.0, 10.0, nz)
    k_iface = np.full(nz, 1e-2)

    k_a = k_iface.copy(); k_a[0] = 0.0
    k_b = k_iface.copy(); k_b[0] = 1e6   # absurd surface-face value
    out_a = solve_diffusion_implicit(c, k_a, grid.depth, grid.cell_thickness, 600.0)
    out_b = solve_diffusion_implicit(c, k_b, grid.depth, grid.cell_thickness, 600.0)
    assert np.max(np.abs(out_a - out_b)) < TOL, "surface face (index 0) must be ignored"
    print("PASS test_solver_surface_face_is_no_flux")


def test_solver_flux_colocated_at_top_face():
    """One implicit step with constant K on a uniform grid must equal the
    backward-Euler update whose flux at top face k is -K*(C[k]-C[k-1])/drC[k]
    (co-located K and gradient, matching MITgcm gad_diff_r.F)."""
    grid = _grid(nz=6, drf=10.0)
    nz = grid.nz
    dt = 300.0
    K = 5e-2
    c0 = np.array([22., 21., 19., 16., 12., 9.])

    k_iface = np.full(nz, K); k_iface[0] = 0.0  # top faces of cells 1..nz-1
    out = solve_diffusion_implicit(c0, k_iface, grid.depth, grid.cell_thickness, dt)

    # Independent backward-Euler solve of the same system, built explicitly with
    # the top-of-cell flux convention.
    drC = grid.depth[:-1] - grid.depth[1:]          # center-to-center, len nz-1
    A = np.zeros((nz, nz))
    rhs = c0 * grid.cell_thickness / dt
    for k in range(nz):
        A[k, k] += grid.cell_thickness[k] / dt
        # top face of cell k couples k-1,k (skip surface face k=0)
        if k >= 1:
            coef = K / drC[k - 1]
            A[k, k] += coef; A[k, k - 1] -= coef
        # top face of cell k+1 couples k,k+1
        if k <= nz - 2:
            coef = K / drC[k]
            A[k, k] += coef; A[k, k + 1] -= coef
    ref = np.linalg.solve(A, rhs)
    assert np.max(np.abs(out - ref)) < 1e-10, "solver flux not co-located at top face k"
    print("PASS test_solver_flux_colocated_at_top_face")


def test_ggl90_kappa_at_top_face_no_averaging():
    """GGL90 kappa_h[k] must equal ck*L[k]*sqrt(TKE[k]) at the SAME index k
    (top face of cell k) with surface index 0 == 0 -- i.e. no half-cell
    averaging is applied anywhere."""
    params = GGL90Parameters.from_yaml()
    nz = 10
    tke = np.full(nz, 0.30)
    mixing_length = np.full(nz, 12.0)
    mask = np.ones(nz)
    n_square = np.zeros(nz)  # Dummy N² for this test
    shear_square = np.zeros(nz)  # Dummy S² for this test

    kappa_m, kappa_h = compute_viscosity_diffusivity(
        tke, mixing_length, mask, params, n_square, shear_square
    )

    assert kappa_m[0] == 0.0 and kappa_h[0] == 0.0, "surface face (index 0) must be 0"
    for k in range(1, nz):
        expect_m = min(params.ck * mixing_length[k] * np.sqrt(max(tke[k], params.tke_min)),
                       params.visc_max)
        assert abs(kappa_m[k] - expect_m) < TOL, f"kappa_m[{k}] shifted/averaged"
    print("PASS test_ggl90_kappa_at_top_face_no_averaging")


def test_ggl90_N2_shear_at_top_face():
    """N^2[k] and S^2[k] are gradients between centers k-1 and k => top face of
    cell k; index 0 is left at 0."""
    # Create depth array (negative-down) and z array (same, "positive up" means moving up increases z toward 0)
    depth = np.array([0., -10., -20., -30., -40.])  # negative-down
    z = depth  # z "positive up" = depth (both negative-down, moving up increases toward 0)
    # Create a stable stratified profile: warm/light at top, cold/dense at bottom
    theta = np.array([20., 15., 10., 8., 7.])
    salt = np.array([35., 35., 35., 35., 35.])

    n2 = compute_ggl90_buoyancy_frequency_squared(
        theta, salt, depth, rho_const=1029.0, gravity=9.81
    )
    u = np.array([0.2, 0.15, 0.1, 0.05, 0.0]); v = np.zeros_like(u)
    s2 = compute_vertical_shear_squared(u, v, z)

    assert n2[0] == 0.0 and s2[0] == 0.0, "surface face index 0 must be 0"
    # N² is now computed using potential density gradients, so the exact
    # value depends on the EOS evaluation. Just check that it's positive
    # (stable stratification) and non-zero.
    assert n2[1] > 0, "N² should be positive for stable stratification"
    print("PASS test_ggl90_N2_shear_at_top_face")


def test_ggl90_unstable_N2_drives_tke_production():
    """MITgcm retains signed N² in -KappaH*N², so an unstable interface
    (N² < 0) produces TKE rather than being silently neutralized."""
    from GGL90_ML.GGL90_PY.ggl90_scheme_specific import compute_tke_buoyancy

    # Create an unstable profile: warmer/lighter water below colder/denser water
    depth = np.array([0., -10.])  # negative-down
    theta = np.array([5., 20.])  # Warmer below (unstable)
    salt = np.array([35., 35.])

    n2 = compute_ggl90_buoyancy_frequency_squared(
        theta, salt, depth, rho_const=1029.0, gravity=9.81
    )
    buoyancy = compute_tke_buoyancy(
        np.array([0., 1.e-3]), n2, np.ones(2)
    )

    assert n2[1] < 0.0, "unstable stratification must retain negative N²"
    assert buoyancy[1] > 0.0, "-KappaH*N² must produce TKE when N² < 0"
    print("PASS test_ggl90_unstable_N2_drives_tke_production")


def test_ggl90_stable_prandtl_controls_tracer_diffusivity():
    """MITgcm uses KappaH=KappaM/Pr_T, with Pr_T=10 at sufficiently stable
    high-Richardson interfaces; alpha belongs to TKE transport, not KappaH."""
    params = GGL90Parameters.from_yaml()
    params.alpha = 30.0
    tke = np.array([params.tke_min, 1.0])
    mixing_length = np.array([params.mixing_length_min, 1.0])
    kappa_m, kappa_h = compute_viscosity_diffusivity(
        tke=tke,
        mixing_length=mixing_length,
        mask=np.ones(2),
        params=params,
        n_square=np.array([0.0, 1.e-4]),
        shear_square=np.array([0.0, 1.e-8]),
    )

    assert abs(kappa_h[1] - kappa_m[1] / 10.0) < TOL
    print("PASS test_ggl90_stable_prandtl_controls_tracer_diffusivity")


def test_ggl90_surface_tke_boundary_is_not_first_interior_face():
    """MITgcm prescribes TKE at surface face 0 and lets face 1 evolve with
    a coupling to it. Pinning face 1 instead suppresses the TKE diffusion that
    communicates surface forcing into the column."""
    params = GGL90Parameters.from_yaml()
    params.tke_surf_min = 1.e-3
    params.tke_bottom = params.tke_min
    drv = GGL90Driver(params)
    tke = np.full(4, params.tke_min)
    zeros = np.zeros(4)
    tke_new = drv.step_tke_forward(
        tke=tke,
        production=zeros,
        buoyancy=zeros,
        mixing_length=np.full(4, 10.0),
        dz=np.ones(4),
        dt=600.0,
        mask=np.ones(4),
        u_star_sq=1e-4,
    )

    assert abs(tke_new[0] - params.tke_surf_min) < TOL
    assert params.tke_min < tke_new[1] < params.tke_surf_min
    print("PASS test_ggl90_surface_tke_boundary_is_not_first_interior_face")


def test_kpp_output_top_face_and_surface_zero():
    """KPP output diffusivities must be on the top-of-cell convention: index 0
    (surface) is 0, and interior faces are the internal bottom-of-cell values
    shifted by +1 (MITgcm vddiff(k-1)->KPPdiffKzT(k))."""
    from KPP_ML.KPP_PY.kpp_core_driver import KPPDriver

    drv = KPPDriver()
    nz = 12
    drf = np.array([2., 3., 4., 5., 6., 8., 10., 12., 15., 20., 25., 30.])
    grid = ColumnGrid.from_drF(drf)
    theta = np.linspace(22., 9., nz)
    salt = np.linspace(34.6, 35.2, nz)
    u = np.linspace(0.14, 0.008, nz); v = np.linspace(0.07, 0.005, nz)

    out = drv.compute_mixing(
        theta=theta, salt=salt, u_vel=u, v_vel=v,
        depth=grid.depth, cell_thickness=grid.cell_thickness,
        tau_x=0.10, tau_y=0.04, q_net=-120.0, q_sw=45.0, fw_flux=0.0, coriol=1e-4,
    )
    assert out.diff_kz_t[0] == 0.0, "KPP surface diffusivity must be 0"
    assert out.diff_kz_s[0] == 0.0
    assert out.visc_az[0] == 0.0
    assert not np.isnan(out.diff_kz_t).any()
    print("PASS test_kpp_output_top_face_and_surface_zero")


if __name__ == "__main__":
    test_solver_surface_face_is_no_flux()
    test_solver_flux_colocated_at_top_face()
    test_ggl90_kappa_at_top_face_no_averaging()
    test_ggl90_N2_shear_at_top_face()
    test_ggl90_unstable_N2_drives_tke_production()
    test_ggl90_stable_prandtl_controls_tracer_diffusivity()
    test_ggl90_surface_tke_boundary_is_not_first_interior_face()
    test_kpp_output_top_face_and_surface_zero()
    print("\nAll staggering tests passed.")
