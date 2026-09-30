"""
Unit tests for the `use_ghat` (KPP_GHAT) compute-vs-apply split -- regression
coverage for 1DMIX-058.

1DMIX-058 root cause (confirmed against
/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_routines.F and
pkg/kpp/kpp_transport_{s,t,ptr}.F, the real MITgcm source this project
ports): `KPP_GHAT` never appears in `kpp_routines.F` -- `blmix` computes the
nonlocal transport coefficient `ghat` UNCONDITIONALLY. `KPP_GHAT` only gates
`kpp_transport_t.F`/`kpp_transport_s.F`, i.e. whether that coefficient is
later added to the tracer's diffusive flux. The Python port used to conflate
the two: `compute_bl_mixing` (kpp_scheme_specific.py) zeroed the `ghat`
*computation* itself whenever `use_ghat` was `False`, matching neither real
MITgcm behaviour (confirmed on a real capture, `global_oce_latlon_720`, whose
own `KPP_OPTIONS.h` has `KPP_GHAT` `#undef`'d yet whose captured `ghat`
output is real and non-degenerate: 376,577 nonzero values, max 205.66) nor
the port's own intent (the port DOES apply `ghat` to a tracer flux, in
`main/shared_column_solver.py::solve_diffusion_implicit`, called from
`main/unified_driver.py::UnifiedColumnDriver._apply_vertical_diffusion` --
Arch's own search for this application site, restricted to
`main/diagnostics.py`, missed it).

The four tests below independently confirm, at the unit level (not via a
real MITgcm capture, which cannot exercise `main/unified_driver.py`'s
application site at all -- see
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py
::test_global_oce_latlon_ghat` for the capture-level regression instead):
  1. `ghat` computation is unaffected by `use_ghat` (matches `blmix`).
  2. `KPPAdapter` threads `use_ghat` into `MixingOutput.apply_ghat`, not into
     the `ghat` array itself.
  3. `UnifiedColumnDriver._apply_vertical_diffusion` actually gates flux
     application on `apply_ghat` (mirrors `kpp_transport_t.F`/
     `kpp_transport_s.F`).
  4. (1DMIX-061) The momentum solve (`u_vel`/`v_vel`) never receives `ghat` at
     all -- real MITgcm applies the nonlocal term only in
     `kpp_transport_t.F`/`kpp_transport_s.F`/`kpp_transport_ptr.F` (tracer
     transport); nothing in `pkg/kpp` applies it to momentum. This is a
     coverage addition, not a fix: the invariant already held (`u_vel`/
     `v_vel`'s calls to `solve_diffusion_implicit` already omit the `ghat=`
     keyword entirely); the other three tests above -- and the whole
     `test_full_scenario_validation.py`/`test_cross_scheme_validation.py`/
     `test_staggering.py` suites -- were measured (1DMIX-061 design) to keep
     passing even under a mutant that routes `u_vel` through
     `ghat_to_apply`, so nothing previously caught a momentum leak on this
     specific boundary.
"""

import dataclasses
import sys
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_parameters import KPPParameters
from KPP.kpp_core_driver import KPPDriver
from main import unified_driver
from main.mixing_adapter import KPPAdapter, MixingOutput
from main.column_grid import ColumnGrid
from main.column_state import ColumnState
from main.unified_driver import UnifiedColumnDriver
from main.shared_column_solver import solve_diffusion_implicit

# A single-column configuration under net surface cooling (unstable forcing,
# bfsfc < 0), the only regime where blmix's nonlocal term is nonzero
# ((1-stable) prefactor) -- confirmed to produce a real nonzero ghat cell
# below by direct measurement before writing this test.
_NZ = 20
_THETA = np.linspace(20.0, 8.0, _NZ)
_SALT = np.linspace(35.5, 34.9, _NZ)
_U = np.linspace(0.05, 0.01, _NZ)
_V = np.linspace(0.03, 0.01, _NZ)
_DEPTH = np.linspace(0.0, -200.0, _NZ)
_DZ = np.full(_NZ, 200.0 / _NZ)
_TAU_X, _TAU_Y = 0.05, 0.0
_Q_NET, _Q_SW, _FW_FLUX = -300.0, 0.0, 0.0
_CORIOL = 1.0e-4


def _run_kpp(use_ghat: bool):
    params = KPPParameters(use_ghat=use_ghat)
    driver = KPPDriver(params)
    return driver.compute_mixing(
        theta=_THETA, salt=_SALT, u_vel=_U, v_vel=_V,
        depth=_DEPTH, cell_thickness=_DZ,
        tau_x=_TAU_X, tau_y=_TAU_Y, q_net=_Q_NET, q_sw=_Q_SW,
        fw_flux=_FW_FLUX, coriol=_CORIOL,
    )


def test_ghat_computed_unconditionally():
    """`compute_bl_mixing` must produce bit-identical, non-degenerate `ghat`
    whether `use_ghat` is True or False -- matching MITgcm's `blmix`, which
    has no `KPP_GHAT` reference at all (1DMIX-058)."""
    out_true = _run_kpp(use_ghat=True)
    out_false = _run_kpp(use_ghat=False)

    assert np.count_nonzero(out_true.ghat) > 0, (
        "test fixture must exercise the nonlocal term -- got all-zero ghat"
    )
    np.testing.assert_array_equal(
        out_true.ghat, out_false.ghat,
        err_msg="use_ghat must not change the computed ghat coefficient "
                "(BLMIX computes it unconditionally in real MITgcm)"
    )
    # hbl and the mixing coefficients themselves are likewise unaffected --
    # use_ghat has no legitimate effect anywhere upstream of flux application.
    assert out_true.hbl == out_false.hbl
    np.testing.assert_array_equal(out_true.diff_kz_t, out_false.diff_kz_t)
    print("PASS test_ghat_computed_unconditionally")


def test_kpp_adapter_apply_ghat_flag():
    """`KPPAdapter` must thread `KPPParameters.use_ghat` into
    `MixingOutput.apply_ghat`, leaving `MixingOutput.ghat` itself the same
    raw, unconditionally-computed array either way."""
    grid = ColumnGrid(depth=_DEPTH, cell_thickness=_DZ)
    state = ColumnState(theta=_THETA.copy(), salt=_SALT.copy(),
                         u_vel=_U.copy(), v_vel=_V.copy())
    forcing = {'tau_x': _TAU_X, 'tau_y': _TAU_Y, 'q_net': _Q_NET,
               'q_sw': _Q_SW, 'fw_flux': _FW_FLUX, 'coriol': _CORIOL}

    out_gate_on = KPPAdapter(KPPDriver(KPPParameters(use_ghat=True))).compute_mixing(
        state, grid, forcing, dt=3600.0)
    out_gate_off = KPPAdapter(KPPDriver(KPPParameters(use_ghat=False))).compute_mixing(
        state, grid, forcing, dt=3600.0)

    assert isinstance(out_gate_on, MixingOutput)
    assert out_gate_on.apply_ghat is True
    assert out_gate_off.apply_ghat is False
    assert np.count_nonzero(out_gate_on.ghat) > 0
    np.testing.assert_array_equal(out_gate_on.ghat, out_gate_off.ghat)
    print("PASS test_kpp_adapter_apply_ghat_flag")


def test_apply_ghat_gate_changes_tracer_evolution():
    """The application-site gate (`UnifiedColumnDriver._apply_vertical_
    diffusion`) must actually change the stepped tracer when `apply_ghat`
    flips, mirroring MITgcm's real `KPP_GHAT` (which changes
    `kpp_transport_t.F`'s output, not `blmix`'s)."""
    ghat = np.zeros(_NZ)
    ghat[3] = 50.0  # a large, nonzero nonlocal coefficient at one interior
                    # cell -- deliberately large enough that its effect on
                    # theta clears floating-point/allclose noise, not just a
                    # physically-typical magnitude
    diff_kz_t = np.full(_NZ, 1.0e-3)
    diff_kz_t[0] = 0.0  # surface face convention

    grid = ColumnGrid(depth=_DEPTH, cell_thickness=_DZ)
    heat_flux = 1.0e-4  # nonzero surface flux -- required for the nonlocal
                        # term to enter at all (solve_diffusion_implicit's
                        # own `ghat is not None and surface_flux != 0.0` gate)

    driver = UnifiedColumnDriver(
        mixing_adapter=None, config_manager=None,
        physical_params={'gravity': 9.81, 'rho_const': 1029.0,
                          'heat_capacity_cp': 3994.0},
    )

    def step(apply_ghat: bool):
        state = ColumnState(theta=_THETA.copy(), salt=_SALT.copy(),
                             u_vel=_U.copy(), v_vel=_V.copy())
        mix_out = MixingOutput(
            visc_az=np.full(_NZ, 1.0e-4), diff_kz_t=diff_kz_t.copy(),
            diff_kz_s=diff_kz_t.copy(), ghat=ghat.copy(),
            apply_ghat=apply_ghat,
        )
        driver._apply_vertical_diffusion(
            state, grid, mix_out,
            kinematic_fluxes={'heat_flux': heat_flux, 'salt_flux': 0.0,
                               'tau_x': 0.0, 'tau_y': 0.0},
            dt=3600.0,
        )
        return state.theta

    theta_gate_on = step(apply_ghat=True)
    theta_gate_off = step(apply_ghat=False)
    theta_no_gate_field = solve_diffusion_implicit(
        c_old=_THETA, k_interface=diff_kz_t, depth=grid.depth,
        thickness=grid.cell_thickness, dt=3600.0,
        surface_flux=heat_flux, ghat=None,
    )

    max_diff = float(np.max(np.abs(theta_gate_on - theta_gate_off)))
    assert max_diff > 1.0e-6, (
        f"apply_ghat=False must change the stepped tracer relative to "
        f"apply_ghat=True when ghat/surface_flux are genuinely nonzero -- "
        f"got max diff {max_diff:.3e}; the gate has no effect, which is the "
        f"exact defect this issue fixed"
    )
    np.testing.assert_allclose(theta_gate_off, theta_no_gate_field, atol=0.0)
    print("PASS test_apply_ghat_gate_changes_tracer_evolution")


def test_momentum_solve_never_receives_ghat():
    """(1DMIX-061) `_apply_vertical_diffusion`'s `u_vel`/`v_vel` calls into
    `solve_diffusion_implicit` must never carry a non-local (`ghat`)
    coefficient -- real MITgcm applies `ghat` only in `kpp_transport_t.F`/
    `kpp_transport_s.F`/`kpp_transport_ptr.F` (tracer transport); KPP's
    counter-gradient term has no momentum analogue anywhere in `pkg/kpp`.

    This spies on the actual keyword arguments `_apply_vertical_diffusion`
    passes into `solve_diffusion_implicit`, rather than comparing evolved
    velocities: a numeric comparison would need a tolerance, would not name
    the invariant on failure, and could be satisfied by a leak small enough
    to hide under that tolerance. `apply_ghat=True` with a large, genuinely
    nonzero `ghat` and nonzero `tau_x`/`tau_y` here means a real leak -- not
    just an omitted keyword -- would be numerically visible if it existed;
    the assertion below fails for the stated reason regardless of magnitude.
    """
    ghat = np.zeros(_NZ)
    ghat[3] = 50.0  # large nonzero nonlocal coefficient (see docstring above)
    diff_kz_t = np.full(_NZ, 1.0e-3)
    diff_kz_t[0] = 0.0  # surface face convention
    visc_az = np.full(_NZ, 1.0e-4)
    visc_az[0] = 0.0

    grid = ColumnGrid(depth=_DEPTH, cell_thickness=_DZ)
    driver = UnifiedColumnDriver(
        mixing_adapter=None, config_manager=None,
        physical_params={'gravity': 9.81, 'rho_const': 1029.0,
                          'heat_capacity_cp': 3994.0},
    )
    state = ColumnState(theta=_THETA.copy(), salt=_SALT.copy(),
                         u_vel=_U.copy(), v_vel=_V.copy())
    # Identify each captured call by the exact array object passed as
    # `c_old`, recorded before `_apply_vertical_diffusion` reassigns
    # `state.theta`/`salt`/`u_vel`/`v_vel` in place.
    original_arrays = {
        'theta': state.theta, 'salt': state.salt,
        'u_vel': state.u_vel, 'v_vel': state.v_vel,
    }
    mix_out = MixingOutput(
        visc_az=visc_az, diff_kz_t=diff_kz_t.copy(),
        diff_kz_s=diff_kz_t.copy(), ghat=ghat.copy(),
        apply_ghat=True,
    )

    calls = []
    real_solve = unified_driver.solve_diffusion_implicit

    def spy(*args, **kwargs):
        assert not args, (
            "test assumes solve_diffusion_implicit is called with keyword "
            "arguments only (true of current _apply_vertical_diffusion); "
            "update the spy if that calling convention changes"
        )
        calls.append(dict(kwargs))
        return real_solve(**kwargs)

    with mock.patch.object(unified_driver, "solve_diffusion_implicit",
                            side_effect=spy):
        driver._apply_vertical_diffusion(
            state, grid, mix_out,
            kinematic_fluxes={'heat_flux': 1.0e-4, 'salt_flux': 1.0e-5,
                               'tau_x': 0.05, 'tau_y': 0.03},
            dt=3600.0,
        )

    assert len(calls) == 4, (
        f"expected exactly 4 solve_diffusion_implicit calls (theta, salt, "
        f"u_vel, v_vel) from _apply_vertical_diffusion, got {len(calls)} -- "
        f"the spy's per-variable matching below assumes this shape"
    )

    def _find_call(name):
        matches = [kw for kw in calls
                   if kw.get('c_old') is original_arrays[name]]
        assert len(matches) == 1, (
            f"expected exactly one solve_diffusion_implicit call whose "
            f"c_old is state.{name} (identity match on the pre-call array "
            f"object), found {len(matches)}"
        )
        return matches[0]

    theta_call = _find_call('theta')
    salt_call = _find_call('salt')
    u_call = _find_call('u_vel')
    v_call = _find_call('v_vel')

    # Sanity: the tracer calls in this fixture DO receive the real nonlocal
    # coefficient -- otherwise a broken fixture (e.g. apply_ghat wired wrong)
    # would make the momentum-side assertion below vacuous.
    assert theta_call.get('ghat') is not None, (
        "fixture must actually exercise a real ghat on the tracer solve -- "
        "got ghat=None for theta, so the momentum check below would not be "
        "a meaningful contrast"
    )
    assert salt_call.get('ghat') is not None

    for name, call in (('u_vel', u_call), ('v_vel', v_call)):
        ghat_arg = call.get('ghat')
        assert ghat_arg is None, (
            f"momentum solve for {name} was given a non-local coefficient "
            f"(ghat={ghat_arg!r}); KPP's ghat is a tracer-transport term "
            f"(real MITgcm applies it only in kpp_transport_t.F/"
            f"kpp_transport_s.F/kpp_transport_ptr.F) with no momentum "
            f"analogue -- ghat must never reach the u_vel/v_vel diffusion "
            f"solve"
        )
    print("PASS test_momentum_solve_never_receives_ghat")


def test_momentum_invariant_to_ghat_value():
    """(1DMIX-063) Quantity-level guard, complementing (not replacing)
    `test_momentum_solve_never_receives_ghat` above.

    That spy only detects one specific leak shape: a `ghat=` keyword
    literally passed into the `u_vel`/`v_vel` `solve_diffusion_implicit`
    calls. The 1DMIX-061 reviewer demonstrated two other implementations of
    the same underlying bug that keep that keyword absent while still
    contaminating momentum -- (b) folding the `ghat` contribution into the
    `visc_az` array handed to the momentum solve, and (c) a post-hoc
    counter-gradient correction applied to `u_vel`/`v_vel` AFTER
    `solve_diffusion_implicit` returns -- and measured both passing all 68
    tests that existed at that time, including the call-level spy.

    This test instead pins the property that is indifferent to *how* a leak
    is implemented: with `apply_ghat=True` held fixed, varying ONLY `ghat`
    (every other input identical between the two runs) must leave the
    stepped `u_vel`/`v_vel` EXACTLY (bit-identical) unchanged. Exact
    equality, not a tolerance, is the right assertion here: real MITgcm's
    `ghat` has no momentum analogue anywhere in `pkg/kpp`, so momentum's
    true dependence on `ghat` is not small -- it is exactly zero. A
    tolerance would silently admit any leak small enough to hide under it,
    which is precisely the class of defect this issue exists to catch; there
    is no physical justification for treating a nonzero momentum response to
    `ghat` as acceptable at any magnitude. The tracer side (`theta`/`salt`)
    is asserted to genuinely change between the same two `ghat` values, so
    this test cannot pass vacuously on a fixture where `ghat` happens to
    have no effect on anything.
    """
    diff_kz_t = np.full(_NZ, 1.0e-3)
    diff_kz_t[0] = 0.0  # surface face convention
    visc_az = np.full(_NZ, 1.0e-4)
    visc_az[0] = 0.0

    ghat_a = np.zeros(_NZ)
    ghat_b = np.zeros(_NZ)
    ghat_b[3] = 50.0  # large nonzero nonlocal coefficient (same fixture
                       # magnitude used throughout this file) -- ghat_a and
                       # ghat_b differ ONLY in this one entry

    grid = ColumnGrid(depth=_DEPTH, cell_thickness=_DZ)
    driver = UnifiedColumnDriver(
        mixing_adapter=None, config_manager=None,
        physical_params={'gravity': 9.81, 'rho_const': 1029.0,
                          'heat_capacity_cp': 3994.0},
    )
    kinematic_fluxes = {'heat_flux': 1.0e-4, 'salt_flux': 1.0e-5,
                         'tau_x': 0.05, 'tau_y': 0.03}

    def step(ghat):
        state = ColumnState(theta=_THETA.copy(), salt=_SALT.copy(),
                             u_vel=_U.copy(), v_vel=_V.copy())
        mix_out = MixingOutput(
            visc_az=visc_az.copy(), diff_kz_t=diff_kz_t.copy(),
            diff_kz_s=diff_kz_t.copy(), ghat=ghat.copy(),
            apply_ghat=True,
        )
        driver._apply_vertical_diffusion(
            state, grid, mix_out, kinematic_fluxes=kinematic_fluxes,
            dt=3600.0,
        )
        return state

    state_a = step(ghat_a)
    state_b = step(ghat_b)

    # Setup check (design's explicit warning): the tracer side must
    # genuinely change between ghat_a and ghat_b, or the momentum assertion
    # below would pass vacuously on a fixture where ghat has no effect on
    # anything.
    theta_diff = float(np.max(np.abs(state_a.theta - state_b.theta)))
    salt_diff = float(np.max(np.abs(state_a.salt - state_b.salt)))
    assert theta_diff > 1.0e-6, (
        f"fixture must exercise a real tracer-side change between the two "
        f"ghat values, got max |theta_a - theta_b| = {theta_diff:.3e} -- a "
        f"guard that cannot demonstrate a nonzero ghat effect on the tracer "
        f"side would pass this test vacuously"
    )
    assert salt_diff > 1.0e-6, (
        f"fixture must exercise a real tracer-side change between the two "
        f"ghat values, got max |salt_a - salt_b| = {salt_diff:.3e}"
    )

    np.testing.assert_array_equal(
        state_a.u_vel, state_b.u_vel,
        err_msg="u_vel changed when ONLY ghat was varied (apply_ghat=True "
                "held fixed in both runs) -- ghat has no momentum analogue "
                "in real MITgcm (kpp_transport_t.F/kpp_transport_s.F/"
                "kpp_transport_ptr.F apply it to tracers only), so u_vel "
                "must be exactly (bit-identical) invariant to ghat "
                "regardless of HOW a leak reaches momentum -- an extra "
                "ghat= keyword, ghat folded into the visc_az array handed "
                "to the momentum solve, or a post-hoc correction applied "
                "after solve_diffusion_implicit returns all violate this "
                "same invariant"
    )
    np.testing.assert_array_equal(
        state_a.v_vel, state_b.v_vel,
        err_msg="v_vel changed when ONLY ghat was varied (apply_ghat=True "
                "held fixed in both runs) -- see the u_vel assertion above "
                "for the invariant being violated"
    )
    print("PASS test_momentum_invariant_to_ghat_value")


def _real_pipeline_step(ghat_fn):
    """Drive the REAL path `KPPAdapter.compute_mixing` ->
    `UnifiedColumnDriver._apply_vertical_diffusion` for one step.

    ghat is varied at the KPPDriver->KPPAdapter boundary only: the
    `KPPDriver.compute_mixing` instance attribute is wrapped so the adapter
    receives a `KPPOutput` identical to the real one except for
    `ghat_fn(ghat)`. The adapter's own code (and the driver body) run
    unmodified, so any ghat-dependent term the adapter or driver adds to a
    momentum-relevant field is exercised. Returns (state, mix_out, ghat_seen).
    """
    kpp_driver = KPPDriver(KPPParameters(use_ghat=True))
    real_compute = kpp_driver.compute_mixing
    seen = {}

    def wrapped(*args, **kwargs):
        out = real_compute(*args, **kwargs)
        out = dataclasses.replace(out, ghat=ghat_fn(out.ghat))
        seen['ghat'] = out.ghat.copy()
        return out

    kpp_driver.compute_mixing = wrapped
    adapter = KPPAdapter(kpp_driver)
    grid = ColumnGrid(depth=_DEPTH, cell_thickness=_DZ)
    state = ColumnState(theta=_THETA.copy(), salt=_SALT.copy(),
                        u_vel=_U.copy(), v_vel=_V.copy())
    forcing = {'tau_x': _TAU_X, 'tau_y': _TAU_Y, 'q_net': _Q_NET,
               'q_sw': _Q_SW, 'fw_flux': _FW_FLUX, 'coriol': _CORIOL}
    mix_out = adapter.compute_mixing(state, grid, forcing, dt=3600.0)
    driver = UnifiedColumnDriver(
        mixing_adapter=adapter, config_manager=None,
        physical_params={'gravity': 9.81, 'rho_const': 1029.0,
                         'heat_capacity_cp': 3994.0},
    )
    # Nonzero kinematic momentum stress (tau/rho_const) and tracer fluxes.
    kinematic_fluxes = {'heat_flux': 1.0e-4, 'salt_flux': 1.0e-5,
                        'tau_x': _TAU_X / 1029.0, 'tau_y': 0.03 / 1029.0}
    driver._apply_vertical_diffusion(state, grid, mix_out,
                                     kinematic_fluxes=kinematic_fluxes,
                                     dt=3600.0)
    return state, mix_out, seen['ghat'], kinematic_fluxes


def test_real_pipeline_momentum_invariant_to_ghat():
    """(1DMIX-064) End-to-end guard: the REAL `KPPAdapter.compute_mixing` ->
    `UnifiedColumnDriver._apply_vertical_diffusion` path, with only `ghat`
    varied (at the KPPDriver->adapter boundary; no hand-built MixingOutput),
    must leave `u_vel`/`v_vel` EXACTLY bit-identical, and the
    momentum-relevant adapter output `visc_az` (the only adapter field feeding
    the u/v solve besides depth/thickness) exactly identical too. This
    catches a ghat-dependent term injected anywhere between the KPP driver's
    output and the momentum solve, including inside the adapter -- the
    boundary 1DMIX-061/063's hand-built witnesses could not see.

    ghat variants (all compared to the unmodified run): x4, x0, "interior"
    (+50 @ face 3, +20 @ face 8), "allfaces" (+10*(1..nz) at every face,
    strictly positive, max > 100) and "signed" (same magnitudes with
    alternating sign). Covers leaks localised by face, by sign, or gated on a
    large ghat value; see docs/model_contract.md for what remains uncovered.

    Non-vacuity is asserted: ghat is genuinely nonzero and differs across the
    runs, the tracers respond to it, and momentum has nonzero forcing and
    actually evolves.
    """
    # Real KPP ghat on this fixture is nonzero ONLY at index 0 (the surface
    # face, which the implicit solve ignores for k_interface), so scaling it
    # alone would leave a momentum-side leak at any interior face numerically
    # invisible (measured, 1DMIX-064). The added variants therefore perturb
    # ghat at interior faces too: "interior" (+50 @3, +20 @8), "allfaces"
    # (every face, strictly positive, up to > 100 so a large-value threshold
    # leak is exercised) and "signed" (same magnitudes, alternating sign, so a
    # leak confined to negative ghat is exercised). Face location, sign and a
    # large-value threshold are what a leak could hide behind (1DMIX-064
    # correction round 1: leaks at faces >= 10, the last face, faces 1-2,
    # negative-only ghat and ghat.max() > 100 all escaped the first version).
    def _interior(g):
        g = g.copy()
        g[3] += 50.0
        g[8] += 20.0
        return g

    def _allfaces(g):
        return g + 10.0 * (1.0 + np.arange(g.size))

    def _signed(g):
        return g + 10.0 * (1.0 + np.arange(g.size)) * (-1.0) ** np.arange(g.size)

    st_base, mo_base, g_base, kin = _real_pipeline_step(lambda g: g)
    variants = {
        "4x": _real_pipeline_step(lambda g: g * 4.0),
        "0x": _real_pipeline_step(lambda g: g * 0.0),
        "interior": _real_pipeline_step(_interior),
        "allfaces": _real_pipeline_step(_allfaces),
        "signed": _real_pipeline_step(_signed),
    }
    st_zero = variants["0x"][0]
    st_big = variants["4x"][0]
    st_int = variants["interior"][0]
    st_all = variants["allfaces"][0]
    st_sgn = variants["signed"][0]
    g_big, g_zero, g_int = (variants[k][2] for k in ("4x", "0x", "interior"))
    g_all, g_sgn = variants["allfaces"][2], variants["signed"][2]

    # Non-vacuity of the varied quantity and of the momentum problem.
    assert np.count_nonzero(g_base) > 0
    assert not np.array_equal(g_base, g_big)
    assert not np.array_equal(g_base, g_zero)
    assert np.count_nonzero(g_int[1:]) > 0 and not np.array_equal(g_base, g_int)
    assert kin['tau_x'] != 0.0 and kin['tau_y'] != 0.0
    assert np.count_nonzero(mo_base.visc_az) > 0
    assert float(np.max(np.abs(st_base.u_vel - _U))) > 0.0
    assert float(np.max(np.abs(st_base.v_vel - _V))) > 0.0
    # allfaces: nonzero at every face incl. the last, and beyond 100.
    assert np.all(g_all[1:] > 0.0) and float(np.max(g_all)) > 100.0
    # signed: genuinely contains negative values (and positive ones).
    assert float(np.min(g_sgn)) < 0.0 < float(np.max(g_sgn))
    assert np.count_nonzero(g_sgn[1:]) == g_sgn.size - 1
    # Tracers must genuinely respond to ghat in the same runs.
    assert float(np.max(np.abs(st_base.theta - st_zero.theta))) > 1.0e-6
    assert float(np.max(np.abs(st_base.theta - st_big.theta))) > 1.0e-6
    assert float(np.max(np.abs(st_base.theta - st_int.theta))) > 1.0e-6
    assert float(np.max(np.abs(st_base.theta - st_all.theta))) > 1.0e-6
    assert float(np.max(np.abs(st_base.theta - st_sgn.theta))) > 1.0e-6

    for label, (st, mo, _g, _k) in variants.items():
        # Adapter contract: momentum-relevant outputs independent of ghat.
        np.testing.assert_array_equal(
            mo_base.visc_az, mo.visc_az,
            err_msg=f"KPPAdapter.compute_mixing visc_az depends on ghat "
                    f"(ghat x1 vs {label})")
        # Pipeline invariant: stepped momentum independent of ghat.
        np.testing.assert_array_equal(
            st_base.u_vel, st.u_vel,
            err_msg=f"real-pipeline u_vel changed with ghat (x1 vs {label})")
        np.testing.assert_array_equal(
            st_base.v_vel, st.v_vel,
            err_msg=f"real-pipeline v_vel changed with ghat (x1 vs {label})")
    print("PASS test_real_pipeline_momentum_invariant_to_ghat")


if __name__ == "__main__":
    test_ghat_computed_unconditionally()
    test_kpp_adapter_apply_ghat_flag()
    test_apply_ghat_gate_changes_tracer_evolution()
    test_momentum_solve_never_receives_ghat()
    test_momentum_invariant_to_ghat_value()
    test_real_pipeline_momentum_invariant_to_ghat()
