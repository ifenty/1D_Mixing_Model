"""
Unit tests for the KPP z-coordinate input guard -- regression coverage for 1DMIX-072.

1DMIX-072: on pressure-coordinate geometry (`global_ocean.cs32x15`,
buoyancyRelation='OCEANICP', `rC`/`rF`/`drF` in Pa) `KPPDriver.compute_mixing`
used to return NaN in 91% of interior cells without raising (first floating-point
error: overflow in `swfrac`'s `exp(-z/d)`). Pressure-coordinate support is
permanently out of scope (1DMIX-040; `docs/model_contract.md` "z-coordinates
only"), so the required behaviour, per the project profile's invalid-input rule,
is an explicit `ValueError`. The guard is
`KPP.kpp_core_driver.validate_zcoordinate_geometry`, called as step 0 of
`KPPDriver.compute_mixing`; it is a pure pre-check and must not change any value
computed for valid input.

These tests check: (1) Pa-scaled columns raise a `ValueError` naming the
quantity, its value and the pressure-coordinate reason (1DMIX-040); (2) the
boundary-valid deep z column (exactly 11,000 m) still runs to finite output while
one just past it raises; (3) the other invalid shapes (non-finite, non-positive
thickness, positive depth) raise; (4) the guard is a pure pre-check -- outputs on
valid input are bit-identical with and without it; (5) the scenario-driving path
(`KPPAdapter`) inherits the rejection. The real `cs32x15` capture geometry is
asserted in
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`.
"""

import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP import kpp_core_driver
from KPP.kpp_core_driver import (
    KPPDriver,
    MAX_ZCOORD_EXTENT_M,
    validate_zcoordinate_geometry,
)
from KPP.kpp_parameters import KPPParameters
from main.column_grid import ColumnGrid
from main.column_state import ColumnState
from main.mixing_adapter import KPPAdapter

# Pressure-coordinate scale factor of MITgcm's `coordFac` = g * rho_0 (Pa per m),
# the factor that turns a metres-scale grid into a Pa-scaled one
# (model_contract.md "z-coordinates only"; `model/src/ini_parms.F`).
_COORD_FAC = 9.81 * 1035.0

_FORCING = dict(tau_x=0.05, tau_y=0.0, q_net=-300.0, q_sw=0.0, fw_flux=0.0, coriol=1.0e-4)


def _column(nz, dz_each):
    """A cell-centre depth (negative down) / thickness pair of `nz` equal cells."""
    dz = np.full(nz, float(dz_each))
    depth = -(np.cumsum(dz) - dz / 2.0)
    return depth, dz


def _state(nz):
    return dict(
        theta=np.linspace(20.0, 2.0, nz),
        salt=np.linspace(35.5, 34.7, nz),
        u_vel=np.linspace(0.05, 0.0, nz),
        v_vel=np.linspace(0.02, 0.0, nz),
    )


def _run(depth, dz, driver=None):
    driver = driver or KPPDriver(KPPParameters())
    return driver.compute_mixing(depth=depth, cell_thickness=dz, **_state(len(dz)), **_FORCING)


# ----------------------------------------------------------------- Pa-scaled input raises

def test_pa_scaled_column_raises_naming_quantity_value_and_reason():
    """A z-coordinate column multiplied by coordFac (Pa-scaled, kept negative-down)
    raises; the message names the offending quantity and its value and cites the
    pressure-coordinate reason and 1DMIX-040."""
    depth, dz = _column(20, 10.0)                       # valid 200 m column
    pa_depth, pa_dz = depth * _COORD_FAC, dz * _COORD_FAC
    with pytest.raises(ValueError) as exc:
        _run(pa_depth, pa_dz)
    msg = str(exc.value)
    assert "max|depth|" in msg
    assert f"{float(np.max(np.abs(pa_depth))):.6g}" in msg          # the value itself
    assert "11000" in msg                                           # the bound
    assert "pressure-coordinate" in msg and "1DMIX-040" in msg


def test_positive_pa_depth_as_in_the_cs32x15_capture_raises():
    """The cs32x15 capture presents as POSITIVE Pa depth decreasing with level
    index (level 0 deepest, 4.9e7 Pa). The sign check fires first, naming the value."""
    pa_depth = np.array([49466694.605501, 42628263.92209099, 251327.843323])
    pa_dz = np.array([7105181.631178, 6571679.735642, 502655.686646])
    with pytest.raises(ValueError) as exc:
        validate_zcoordinate_geometry(pa_depth, pa_dz)
    msg = str(exc.value)
    assert "max(depth)" in msg and f"{float(pa_depth.max()):.6g}" in msg
    assert "pressure-coordinate" in msg and "1DMIX-040" in msg


def test_pa_thickness_alone_raises_naming_thickness():
    """Metre-valued depth with Pa-valued thickness is still rejected, by the
    thickness bounds (sum first), naming the offending quantity."""
    depth, dz = _column(5, 10.0)
    with pytest.raises(ValueError) as exc:
        validate_zcoordinate_geometry(depth, dz * _COORD_FAC)
    assert "sum(cell_thickness)" in str(exc.value)
    assert "1DMIX-040" in str(exc.value)


# ---------------------------------------------------- boundary-valid deep z column passes

def test_boundary_valid_deep_z_column_passes_and_is_finite():
    """The deepest admissible column: 11 cells of 1000 m, so sum(dz) == 11,000 m
    and the deepest node sits exactly at -11,000 m (no check may fire at equality).
    Runs to finite mixing coefficients."""
    nz = 11
    dz = np.full(nz, 1000.0)
    depth = -np.arange(1, nz + 1) * 1000.0               # -1000 ... -11000
    assert float(np.max(np.abs(depth))) == MAX_ZCOORD_EXTENT_M
    assert float(dz.sum()) == MAX_ZCOORD_EXTENT_M
    validate_zcoordinate_geometry(depth, dz)             # returns None, no raise
    out = _run(depth, dz)
    for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat"):
        assert np.all(np.isfinite(getattr(out, name))), name
    assert np.isfinite(out.hbl)


def test_just_past_boundary_raises():
    """Every extent 0.1% past 11,000 m: max|depth| is checked first and is named."""
    nz = 11
    dz = np.full(nz, 1000.0) * 1.001
    depth = -np.arange(1, nz + 1) * 1000.0 * 1.001
    with pytest.raises(ValueError, match=r"max\|depth\|=11011"):
        validate_zcoordinate_geometry(depth, dz)


def test_depth_within_bound_but_thickness_sum_past_bound_raises():
    """max|depth| = 10,500 passes its own bound, sum(cell_thickness) = 11,001 does not."""
    depth = np.array([-500.0, -10500.0])
    dz = np.array([1.0, 11000.0])
    with pytest.raises(ValueError, match=r"sum\(cell_thickness\)=11001"):
        validate_zcoordinate_geometry(depth, dz)


def test_surface_node_at_zero_depth_is_admissible():
    """Existing fixtures (`linspace(0, -H, nz)`, ghat-gate, cross-scheme) put the
    first node at depth exactly 0.0; that must not be rejected."""
    nz = 20
    depth = np.linspace(0.0, -200.0, nz)
    dz = np.full(nz, 200.0 / nz)
    validate_zcoordinate_geometry(depth, dz)
    assert np.all(np.isfinite(_run(depth, dz).visc_az))


# ------------------------------------------------------------ other invalid geometry raises

@pytest.mark.parametrize("bad_depth, bad_dz, expect", [
    (lambda d: np.where(np.arange(len(d)) == 2, np.nan, d), lambda z: z, "must be finite"),
    (lambda d: d, lambda z: np.where(np.arange(len(z)) == 1, np.inf, z), "must be finite"),
    (lambda d: d, lambda z: np.where(np.arange(len(z)) == 3, 0.0, z), "min(cell_thickness)=0"),
    (lambda d: d, lambda z: np.where(np.arange(len(z)) == 3, -5.0, z), "min(cell_thickness)=-5"),
    (lambda d: d + 25.0, lambda z: z, "max(depth)="),           # positive-down (depth[0]=+20 here)
])
def test_other_invalid_geometry_raises(bad_depth, bad_dz, expect):
    depth, dz = _column(8, 10.0)
    with pytest.raises(ValueError) as exc:
        validate_zcoordinate_geometry(bad_depth(depth), bad_dz(dz))
    assert expect in str(exc.value)
    assert "1DMIX-040" in str(exc.value)


# ------------------------------------------------------------------- pure pre-check

def test_guard_is_pure_pre_check_outputs_bit_identical_with_and_without_it():
    """On valid input, every computed output equals (bit for bit) the output with
    the guard replaced by a no-op: the guard changes no computed value."""
    depth, dz = _column(20, 10.0)
    depth_before, dz_before = depth.copy(), dz.copy()
    guarded = _run(depth, dz)
    with mock.patch.object(kpp_core_driver, "validate_zcoordinate_geometry", lambda *a, **k: None):
        unguarded = _run(depth, dz)
    for name in ("visc_az", "diff_kz_s", "diff_kz_t", "ghat", "bulk_ri", "shear_sq",
                 "buoy_freq_sq", "dVsq", "Ritop"):
        np.testing.assert_array_equal(getattr(guarded, name), getattr(unguarded, name), err_msg=name)
    assert guarded.hbl == unguarded.hbl
    assert guarded.ustar == unguarded.ustar and guarded.bfsfc == unguarded.bfsfc
    np.testing.assert_array_equal(depth, depth_before)             # inputs untouched
    np.testing.assert_array_equal(dz, dz_before)


def test_guard_is_called_before_any_physics():
    """The guard runs as the first step of compute_mixing: a bad geometry raises
    before the (otherwise) forcing-mode ValueError of a call with no forcing at all."""
    depth, dz = _column(5, 10.0)
    with pytest.raises(ValueError, match="1DMIX-040"):
        KPPDriver(KPPParameters()).compute_mixing(
            depth=depth * _COORD_FAC, cell_thickness=dz * _COORD_FAC, **_state(5))


# ------------------------------------------------------ scenario-driving path inherits it

def test_kpp_adapter_rejects_pa_scaled_grid():
    """`KPPAdapter.compute_mixing` (the scenario-driving path) forwards
    `grid.depth`/`grid.cell_thickness` to the driver and so inherits the rejection."""
    dz_pa = np.full(10, 10.0 * _COORD_FAC)
    grid = ColumnGrid.from_drF(dz_pa)
    st = _state(10)
    state = ColumnState(theta=st["theta"], salt=st["salt"], u_vel=st["u_vel"], v_vel=st["v_vel"])
    with pytest.raises(ValueError, match="1DMIX-040"):
        KPPAdapter(KPPDriver(KPPParameters())).compute_mixing(state, grid, _FORCING, dt=3600.0)
