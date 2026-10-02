"""
Tests for `scripts/tracer_point_inputs.py` -- 1DMIX-071.

MITgcm forms the shear at a tracer point from the velocities of the (i, i+1), (j, j+1) faces and, for
KPP's smoothed quantities, of the 3x3 neighbourhood; the replays used to hand the single-column
port only uVel(i,j), vVel(i,j). `scripts/tracer_point_inputs.py` rebuilds MITgcm's quantities from the
neighbouring columns of a capture.

Part 1 (synthetic, never skips): the building blocks against independent scalar-loop transcriptions
of the Fortran text, and `smooth_horiz` against hand-computed numbers (the smoothed dbloc is not
captured, so this is the only direct check of its arithmetic; it is otherwise validated only through its
effect on KPP outputs, see KPP_VALIDATION_RESULTS.md).

Part 2 (captures): the reconstruction reproduces what MITgcm captured -- GGL90 `vertical_shear`
(ggl90_calc.F:541-556), KPP `shear_sq` (kpp_calc.F:459-495) and `dVsq` (kpp_forcing_surf.F:463-504) --
on every in-scope multi-column capture, in interior, tile-edge and domain-edge columns, and the
periodic-wrap neighbour rule is the one that does it (a zero-fill rule fails at wet domain edges).
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / 'scripts'))
sys.path.insert(0, str(_ROOT.parent / 'Vertical_Mixing_Models'))

import tracer_point_inputs as tpi  # noqa: E402

_GGL_IN = _ROOT / 'GGL90_port_validation' / 'inputs_from_mitgcm'
_GGL_OUT = _ROOT / 'GGL90_port_validation' / 'outputs_from_mitgcm'
_KPP_IN = _ROOT / 'KPP_port_validation' / 'inputs_from_mitgcm'
_KPP_OUT = _ROOT / 'KPP_port_validation' / 'outputs_from_mitgcm'


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"Required MITgcm capture not found: {path}")


# ==================================================================== Part 1: synthetic

def test_neighbour_wraps_or_reads_zero():
    a = np.arange(12.0).reshape(1, 3, 4, 1)          # (t, x=3, y=4, z=1), a[0,x,y,0] = 4x + y
    w = tpi.neighbour(a, 1, 0)
    np.testing.assert_array_equal(w[0, :, :, 0], np.roll(a[0, :, :, 0], -1, axis=0))
    z = tpi.neighbour(a, 1, 0, periodic_x=False)
    np.testing.assert_array_equal(z[0, :2, :, 0], a[0, 1:, :, 0])
    np.testing.assert_array_equal(z[0, 2, :, 0], np.zeros(4))
    z = tpi.neighbour(a, 0, -1, periodic_y=False)
    np.testing.assert_array_equal(z[0, :, 1:, 0], a[0, :, :3, 0])
    np.testing.assert_array_equal(z[0, :, 0, 0], np.zeros(3))
    np.testing.assert_array_equal(tpi.neighbour(a, 0, 0), a)


def _rand_uv(seed, shape=(2, 4, 3, 5)):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(shape), rng.standard_normal(shape)


@pytest.mark.parametrize('periodic', [True, False])
def test_tracer_point_velocities_match_scalar_loop(periodic):
    u, v = _rand_uv(1)
    ubar, vbar = tpi.tracer_point_velocities(u, v, periodic, periodic)
    nt, nx, ny, nz = u.shape
    for t in range(nt):
        for i in range(nx):
            for j in range(ny):
                ip1, jp1 = i + 1, j + 1
                if periodic:
                    ip1, jp1 = ip1 % nx, jp1 % ny
                un = u[t, ip1, j] if ip1 < nx else np.zeros(nz)
                vn = v[t, i, jp1] if jp1 < ny else np.zeros(nz)
                np.testing.assert_array_equal(ubar[t, i, j], 0.5 * (u[t, i, j] + un))
                np.testing.assert_array_equal(vbar[t, i, j], 0.5 * (v[t, i, j] + vn))


def _fortran_shsq(u, v, t, i, j, k, smooth, nx, ny):
    """kpp_calc.F:468-495 written as scalar Fortran, periodic indices (reference, not the vectorised code)."""
    def U(ii, jj, kk):
        return u[t, ii % nx, jj % ny, kk]

    def V(ii, jj, kk):
        return v[t, ii % nx, jj % ny, kk]
    ip1, im1, jp1, jm1 = i + 1, i - 1, j + 1, j - 1
    kp1 = k + 1
    sh = 0.5 * ((U(i, j, k) - U(i, j, kp1)) * (U(i, j, k) - U(i, j, kp1))
                + (U(ip1, j, k) - U(ip1, j, kp1)) * (U(ip1, j, k) - U(ip1, j, kp1))
                + (V(i, j, k) - V(i, j, kp1)) * (V(i, j, k) - V(i, j, kp1))
                + (V(i, jp1, k) - V(i, jp1, kp1)) * (V(i, jp1, k) - V(i, jp1, kp1)))
    if smooth:
        sh = 0.5 * sh + 0.125 * (
            (U(i, jm1, k) - U(i, jm1, kp1)) * (U(i, jm1, k) - U(i, jm1, kp1))
            + (U(ip1, jm1, k) - U(ip1, jm1, kp1)) * (U(ip1, jm1, k) - U(ip1, jm1, kp1))
            + (U(i, jp1, k) - U(i, jp1, kp1)) * (U(i, jp1, k) - U(i, jp1, kp1))
            + (U(ip1, jp1, k) - U(ip1, jp1, kp1)) * (U(ip1, jp1, k) - U(ip1, jp1, kp1))
            + (V(im1, j, k) - V(im1, j, kp1)) * (V(im1, j, k) - V(im1, j, kp1))
            + (V(im1, jp1, k) - V(im1, jp1, kp1)) * (V(im1, jp1, k) - V(im1, jp1, kp1))
            + (V(ip1, j, k) - V(ip1, j, kp1)) * (V(ip1, j, k) - V(ip1, j, kp1))
            + (V(ip1, jp1, k) - V(ip1, jp1, kp1)) * (V(ip1, jp1, k) - V(ip1, jp1, kp1)))
    return sh


@pytest.mark.parametrize('smooth', [False, True])
def test_kpp_shsq_matches_scalar_fortran_transcription(smooth):
    u, v = _rand_uv(2)
    nt, nx, ny, nz = u.shape
    got = tpi.kpp_shsq(u, v, smooth)
    assert got.shape == u.shape
    np.testing.assert_array_equal(got[..., nz - 1], 0.0)          # shsq(Nr) = 0 (loop to Nrm1)
    for t in range(nt):
        for i in range(nx):
            for j in range(ny):
                for k in range(nz - 1):
                    assert got[t, i, j, k] == _fortran_shsq(u, v, t, i, j, k, smooth, nx, ny), (t, i, j, k)


def test_kpp_dvsq_matches_scalar_fortran_transcription():
    u, v = _rand_uv(3)
    nt, nx, ny, nz = u.shape
    got = tpi.kpp_dvsq(u, v)
    for t in range(nt):
        for i in range(nx):
            for j in range(ny):
                ip1, jp1 = (i + 1) % nx, (j + 1) % ny
                for k in range(nz):       # kpp_forcing_surf.F:472-480
                    ref = 0.5 * ((u[t, i, j, 0] - u[t, i, j, k]) * (u[t, i, j, 0] - u[t, i, j, k])
                                 + (u[t, ip1, j, 0] - u[t, ip1, j, k]) * (u[t, ip1, j, 0] - u[t, ip1, j, k])
                                 + (v[t, i, j, 0] - v[t, i, j, k]) * (v[t, i, j, 0] - v[t, i, j, k])
                                 + (v[t, i, jp1, 0] - v[t, i, jp1, k]) * (v[t, i, jp1, 0] - v[t, i, jp1, k]))
                    assert got[t, i, j, k] == ref
    np.testing.assert_array_equal(got[..., 0], 0.0)


def _smooth(fld2d, mask2d, **kw):
    """smooth_horiz on a single (x, y) level: arrays shaped (1, x, y, 1)."""
    return tpi.smooth_horiz(fld2d[None, :, :, None], mask2d[None, :, :, None].astype(bool),
                            periodic_x=False, periodic_y=False, **kw)[0, :, :, 0]


def test_smooth_horiz_hand_computed():
    """kpp_routines.F:1318-1398 on a 3x3 all-wet block (fld[x][y] = 3x + y + 1), non-periodic so the cells
    beyond the edge are dry (mask 0), computed by hand from the weights p25/p125/p0625:
      centre  : tempVar = .25 + 4*.125 + 4*.0625 = 1;  num = .25*5 + .125*(2+8+4+6) + .0625*(1+3+7+9) = 5      -> 5
      corner (0,0): tempVar = .25 + .125*2 + .0625 = .5625; num = .25*1 + .125*(4+2) + .0625*5 = 1.3125      -> 7/3
      edge (1,0)  : tempVar = .25 + .125*3 + .0625*2 = .75;   num = .25*4 + .125*(1+7+5) + .0625*(2+8) = 3.25 -> 13/3
      corner (2,2): tempVar = .5625; num = .25*9 + .125*(6+8) + .0625*5 = 4.3125                              -> 23/3
    """
    fld = np.array([[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]])
    out = _smooth(fld, np.ones((3, 3)))
    assert out[1, 1] == pytest.approx(5.0, abs=1e-15)
    assert out[0, 0] == pytest.approx(7.0 / 3.0, abs=1e-15)
    assert out[1, 0] == pytest.approx(13.0 / 3.0, abs=1e-15)
    assert out[2, 2] == pytest.approx(23.0 / 3.0, abs=1e-15)     # corner (2,2): num 4.3125 / tempVar .5625


def test_smooth_horiz_land_masking_and_threshold():
    fld = np.array([[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]])
    # dry centre: tempVar = 0 + 4*.125 + 4*.0625 = .75 >= .25 -> average of the 8 wet neighbours
    # (.125*(2+8+4+6) + .0625*(1+3+7+9)) / .75 = 3.75/.75 = 5 (the dry centre's own value is masked out)
    mask = np.ones((3, 3)); mask[1, 1] = 0
    assert _smooth(fld, mask)[1, 1] == pytest.approx(5.0, abs=1e-15)
    fld2 = fld.copy(); fld2[1, 1] = 1.0e6           # a dry cell's value never enters
    assert _smooth(fld2, mask)[1, 1] == pytest.approx(5.0, abs=1e-15)
    # an isolated wet cell (all neighbours dry): tempVar = .25 >= .25 -> its own value
    mask = np.zeros((3, 3)); mask[1, 1] = 1
    assert _smooth(fld, mask)[1, 1] == pytest.approx(5.0, abs=1e-15)
    # dry centre with a single wet corner: tempVar = .0625 < .25 -> field unchanged
    mask = np.zeros((3, 3)); mask[0, 0] = 1
    assert _smooth(fld, mask)[1, 1] == fld[1, 1]


def test_kpp_dbloc_smooth_uses_next_level_mask_and_leaves_bottom_raw():
    """dbloc(k) is smoothed with maskC(k+1) (kpp_calc.F:282-287): where level k+1 is dry the value is
    returned raw, and the last level is never smoothed."""
    rng = np.random.default_rng(5)
    nz = 4
    raw = rng.standard_normal((1, 4, 4, nz))
    wet = np.ones((1, 4, 4, nz), dtype=bool)
    wet[0, 2, 2, 2:] = False                          # column (2,2) is 2 levels deep
    out = tpi.kpp_dbloc_smooth(raw, wet)
    np.testing.assert_array_equal(out[..., nz - 1], raw[..., nz - 1])
    assert out[0, 2, 2, 1] == raw[0, 2, 2, 1]         # level k=1: k+1 = 2 is dry here -> raw
    assert out[0, 1, 1, 0] != raw[0, 1, 1, 0]         # an interior wet interface is smoothed
    # the dry-below column does not contribute to its neighbours at level k=1 (mask(k+1)=0 there)
    manual = tpi.smooth_horiz(raw[..., 1:2], wet[..., 2:3])
    assert out[0, 1, 1, 1] == manual[0, 1, 1, 0]


@pytest.mark.parametrize('flag', ['estimate_uref', 'smooth_dvsq', 'smooth_dens', 'smooth_visc', 'smooth_diff'])
def test_unsupported_kpp_options_raise_not_implemented(flag):
    tpi.check_supported_kpp_options({'smooth_shsq': 1, 'smooth_dbloc': 1, flag: 0})
    with pytest.raises(NotImplementedError, match='tracer_point_inputs=False'):
        tpi.check_supported_kpp_options({'smooth_shsq': 1, flag: 1})


# ==================================================================== Part 2: captures

def _edge_classes(nx, ny, snx, sny, radius):
    """0 interior, 1 tile edge, 2 domain edge, for a stencil reaching `radius` columns (radius=1:
    both sides; radius=-1 means only the +i/+j side, as the GGL90 shear and unsmoothed KPP shsq)."""
    ii = np.arange(nx)[:, None] * np.ones((1, ny), dtype=int)
    jj = np.arange(ny)[None, :] * np.ones((nx, 1), dtype=int)
    cls = np.zeros((nx, ny), dtype=int)
    if radius == 1:
        cls[(ii % snx == snx - 1) | (jj % sny == sny - 1) | (ii % snx == 0) | (jj % sny == 0)] = 1
        cls[(ii == nx - 1) | (jj == ny - 1) | (ii == 0) | (jj == 0)] = 2
    else:
        cls[(ii % snx == snx - 1) | (jj % sny == sny - 1)] = 1
        cls[(ii == nx - 1) | (jj == ny - 1)] = 2
    return cls


def _max_rel(a, b):
    d = np.abs(a - b)
    with np.errstate(divide='ignore', invalid='ignore'):
        rel = np.where(np.abs(b) > 0, d / np.abs(b), np.where(d > 0, np.inf, 0.0))
    return float(rel.max()) if rel.size else 0.0


# (stem, tile sNx, sNy, time slice, expected tile-edge columns exist)
_GGL_CAPTURES = [
    ('isomip_12', 25, 25, slice(0, 12)),
    ('global_ocean_90x40x15_idemix_10', 10, 10, slice(0, 10)),
    ('lab_sea_999', 20, 16, slice(0, 300)),
    ('lab_sea_6mo', 20, 16, slice(2000, 2100)),
]


@pytest.mark.parametrize('stem,snx,sny,tsl', _GGL_CAPTURES)
def test_ggl90_tracer_point_shear_reproduces_captured_vertical_shear(stem, snx, sny, tsl):
    """Rebuilt (d ubar/dz)^2 + (d vbar/dz)^2 == MITgcm's captured `vertical_shear` (ggl90_calc.F:541-556,
    calcMeanVertShear=0) to roundoff in interior, tile-edge and domain-edge columns: measured max relative
    difference <= 8.1e-16 on every capture and class (2026-10-02). The column-local value the replay used
    to feed is off by a median 0.02-0.74. Bound asserted: 1e-14."""
    _require(_GGL_IN / f'mitgcm_ggl90_inputs_{stem}.nc')
    _require(_GGL_OUT / f'mitgcm_ggl90_outputs_{stem}.nc')
    ins = xr.open_dataset(_GGL_IN / f'mitgcm_ggl90_inputs_{stem}.nc').isel(time=tsl).load()
    outs = xr.open_dataset(_GGL_OUT / f'mitgcm_ggl90_outputs_{stem}.nc').isel(time=tsl).load()
    assert int(ins.attrs['calcMeanVertShear']) == 0
    u, v = ins['u_velocity'].values, ins['v_velocity'].values
    theta = ins['temperature'].values
    zc = ins['depth'].values
    drc = np.abs(zc[:-1] - zc[1:])
    ubar, vbar = tpi.tracer_point_velocities(u, v)
    rebuilt = ((ubar[..., :-1] - ubar[..., 1:]) / drc) ** 2 + ((vbar[..., :-1] - vbar[..., 1:]) / drc) ** 2
    local = ((u[..., :-1] - u[..., 1:]) / drc) ** 2 + ((v[..., :-1] - v[..., 1:]) / drc) ** 2
    captured = outs['vertical_shear'].values[..., 1:]
    wet = (theta[..., 1:] != 0) & (theta[..., :-1] != 0)
    nt, nx, ny, _ = u.shape
    cls = np.broadcast_to(_edge_classes(nx, ny, snx, sny, -1)[None, :, :, None], wet.shape)
    for c, name in enumerate(('interior', 'tile-edge', 'domain-edge')):
        sel = wet & (cls == c)
        if not sel.any():
            assert not (c == 1 and (nx > snx or ny > sny)), f"{stem}: expected tile-edge columns"
            continue
        assert _max_rel(rebuilt[sel], captured[sel]) < 1e-14, f"{stem} {name}"
    assert float(np.median(np.abs(local - captured)[wet & (captured > 1e-14)] / captured[wet & (captured > 1e-14)])) > 0.01


def test_ggl90_periodic_wrap_is_the_rule_zero_fill_fails_at_wet_domain_edges():
    """global_ocean_90x40x15 is periodic in x with wet columns at the edge: a zero-fill rule is wrong there
    (2,790 of 3,830 domain-edge interfaces off by >1e-9 relative, measured 2026-10-02)."""
    stem = 'global_ocean_90x40x15_idemix_10'
    _require(_GGL_IN / f'mitgcm_ggl90_inputs_{stem}.nc')
    ins = xr.open_dataset(_GGL_IN / f'mitgcm_ggl90_inputs_{stem}.nc').isel(time=slice(0, 3)).load()
    outs = xr.open_dataset(_GGL_OUT / f'mitgcm_ggl90_outputs_{stem}.nc').isel(time=slice(0, 3)).load()
    u, v, theta = ins['u_velocity'].values, ins['v_velocity'].values, ins['temperature'].values
    drc = np.abs(np.diff(ins['depth'].values))
    ubar, vbar = tpi.tracer_point_velocities(u, v, periodic_x=False, periodic_y=False)
    rebuilt = ((ubar[..., :-1] - ubar[..., 1:]) / drc) ** 2 + ((vbar[..., :-1] - vbar[..., 1:]) / drc) ** 2
    captured = outs['vertical_shear'].values[..., 1:]
    wet = (theta[..., 1:] != 0) & (theta[..., :-1] != 0)
    nx, ny = u.shape[1:3]
    edge = np.zeros(wet.shape, dtype=bool)
    edge[:, nx - 1, :, :] = True
    sel = wet & edge
    assert sel.sum() > 100
    assert _max_rel(rebuilt[sel], captured[sel]) > 1e-3


# (stem, sNx, sNy, time slice)
_KPP_CAPTURES = [
    ('lab_sea_1000_0820T0946', 20, 16, slice(0, 100)),
    ('lab_sea_6mo', 20, 16, slice(2000, 2100)),
    ('seaice_obcs_1dmix034', 5, 8, slice(0, 5)),
    ('global_oce_latlon_720', 45, 20, slice(0, 10)),
    ('global_oce_latlon_720', 45, 20, slice(700, 710)),
    ('global_ocean_90x40x15_10', 10, 10, slice(0, 10)),
]


@pytest.mark.parametrize('stem,snx,sny,tsl', _KPP_CAPTURES)
def test_kpp_tracer_point_shsq_dvsq_reproduce_captured_values(stem, snx, sny, tsl):
    """`kpp_shsq` / `kpp_dvsq` == MITgcm's captured `shear_sq` / `dVsq` (smoothing flags read from the
    capture's attributes: smooth_shsq=1 on lab_sea, seaice_obcs and 90x40, 0 on global_oce_latlon;
    smooth_dvsq=0 and estimate_uref=0 everywhere): measured max relative difference 0.0 (bit identical) in
    interior, tile-edge and domain-edge columns on every capture/window, 2026-10-02; asserted < 1e-14.
    The column-local `du**2+dv**2` the replay used to feed differs by a median 0.19-0.46 (shear_sq)
    / 0.22-0.46 (dVsq)."""
    _require(_KPP_IN / f'mitgcm_kpp_inputs_{stem}.nc')
    _require(_KPP_OUT / f'mitgcm_kpp_outputs_{stem}.nc')
    ins = xr.open_dataset(_KPP_IN / f'mitgcm_kpp_inputs_{stem}.nc').isel(time=tsl).load()
    outs = xr.open_dataset(_KPP_OUT / f'mitgcm_kpp_outputs_{stem}.nc').isel(time=tsl).load()
    tpi.check_supported_kpp_options(ins.attrs)
    smooth = bool(int(ins.attrs['smooth_shsq']))
    u, v, theta = ins['u_velocity'].values, ins['v_velocity'].values, ins['temperature'].values
    shsq = tpi.kpp_shsq(u, v, smooth)
    dvsq = tpi.kpp_dvsq(u, v)
    col_wet = (theta[..., 0] != 0)[..., None]
    nt, nx, ny, nz = u.shape
    for name, got, ref, radius_smooth in (('shear_sq', shsq[..., :-1], outs['shear_sq'].values[..., :-1], smooth),
                                          ('dVsq', dvsq, outs['dVsq'].values, False)):
        cls = np.broadcast_to(_edge_classes(nx, ny, snx, sny, 1 if radius_smooth else -1)[None, :, :, None],
                              ref.shape)
        wet = np.broadcast_to(col_wet, ref.shape)
        seen = []
        for c, cname in enumerate(('interior', 'tile-edge', 'domain-edge')):
            sel = wet & (cls == c)
            if sel.any():
                assert _max_rel(got[sel], ref[sel]) < 1e-14, f"{stem} {name} {cname}"
                seen.append(c)
        assert 0 in seen
    local = (u[..., :-1] - u[..., 1:]) ** 2 + (v[..., :-1] - v[..., 1:]) ** 2
    ref = outs['shear_sq'].values[..., :-1]
    m = np.broadcast_to(col_wet, ref.shape) & (ref > 0)
    assert float(np.median(np.abs(local - ref)[m] / ref[m])) > 0.05


def test_kpp_zero_fill_rule_fails_at_wet_domain_edges():
    """seaice_obcs follows the periodic exchange too (the OBC edge columns' neighbours are the opposite
    edge): a zero-fill rule leaves 245 of 1,870 domain-edge shear_sq cells off by >1e-9 (measured)."""
    stem = 'seaice_obcs_1dmix034'
    _require(_KPP_IN / f'mitgcm_kpp_inputs_{stem}.nc')
    ins = xr.open_dataset(_KPP_IN / f'mitgcm_kpp_inputs_{stem}.nc').load()
    outs = xr.open_dataset(_KPP_OUT / f'mitgcm_kpp_outputs_{stem}.nc').load()
    u, v, theta = ins['u_velocity'].values, ins['v_velocity'].values, ins['temperature'].values
    got = tpi.kpp_shsq(u, v, True, periodic_x=False, periodic_y=False)[..., :-1]
    ref = outs['shear_sq'].values[..., :-1]
    nx, ny = u.shape[1:3]
    edge = np.zeros(ref.shape, dtype=bool)
    edge[:, [0, nx - 1], :, :] = True
    edge[:, :, [0, ny - 1], :] = True
    sel = edge & np.broadcast_to((theta[..., 0] != 0)[..., None], ref.shape)
    assert _max_rel(got[sel], ref[sel]) > 1e-3
