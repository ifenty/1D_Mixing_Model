"""
Unit tests for the `use_doublediff` (KPPuseDoubleDiff) unimplemented-option
guard -- regression coverage for 1DMIX-059.

1DMIX-059 root cause (confirmed against
/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_routines.F and
pkg/kpp/kpp_readparms.F, the real MITgcm source this project ports):
`KPP_DOUBLEDIFF` (kpp_routines.F, invoked from kpp_calc.F only when
`EXCLUDE_KPP_DOUBLEDIFF` is `#undef` -- MITgcm's own default -- AND the
runtime flag `KPPuseDoubleDiff` is `.TRUE.`) adds double-diffusive
(salt-fingering / diffusive-convection) contributions to the interior mixing
coefficients. This Python port declared both flags
(`KPPParameters.exclude_doublediff`, `KPPParameters.use_doublediff`) and two
of the associated physical constants (`Rrho0`, `dsfmax`) but never
implemented the physics: `KPP/kpp_routines.py::ri_iwmix` (this port's
`Ri_iwmix`-equivalent) has no code path referencing double diffusion at all,
and `Rrho0`/`dsfmax` have no consumer anywhere in the port (confirmed by
direct read/grep). Unlike the port's other unimplemented options
(`allow_shelfice`, an unported `use_salt_plume` configuration), this one
carried no guard at all -- a caller requesting it got silently-wrong physics
(missing double diffusion) with no error, warning, or log line.

Only `use_doublediff` (the runtime switch) is guarded, not
`exclude_doublediff` (the compile-time exclusion switch): real MITgcm
defaults `EXCLUDE_KPP_DOUBLEDIFF` to `#undef` (i.e. the double-diffusion code
IS compiled in by default), so this port's `exclude_doublediff=False` default
is not a misrepresentation -- the port simply never implements that code
regardless of this flag's value. `exclude_doublediff=True` ("do not compile
this code") is trivially satisfied either way. It is `use_doublediff=True`
("apply this physics at runtime") that this port cannot honour and must not
silently ignore.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_parameters import KPPParameters


def test_use_doublediff_true_raises():
    """`use_doublediff=True` (KPPuseDoubleDiff, the runtime switch) must
    raise NotImplementedError -- this port has no double-diffusion physics
    to honour the request with."""
    with pytest.raises(NotImplementedError, match="double diffusion"):
        KPPParameters(use_doublediff=True)
    print("PASS test_use_doublediff_true_raises")


def test_use_doublediff_default_does_not_raise():
    """The default configuration (`use_doublediff=False`, matching this
    port's shipped YAML and MITgcm's own runtime default,
    kpp_readparms.F:84) must construct without error."""
    params = KPPParameters()
    assert params.use_doublediff is False
    print("PASS test_use_doublediff_default_does_not_raise")


def test_exclude_doublediff_true_does_not_raise():
    """`exclude_doublediff` (EXCLUDE_KPP_DOUBLEDIFF, the compile-time
    exclusion flag) must NOT trip the guard in either direction -- it is
    `use_doublediff`, not this flag, that this issue guards. Setting it True
    ("do not compile double diffusion") is trivially satisfied by a port that
    never compiles it in regardless."""
    params_true = KPPParameters(exclude_doublediff=True)
    params_false = KPPParameters(exclude_doublediff=False)
    assert params_true.exclude_doublediff is True
    assert params_false.exclude_doublediff is False
    print("PASS test_exclude_doublediff_true_does_not_raise")


def test_use_doublediff_true_from_yaml_override_raises():
    """A user YAML override that turns on `use_doublediff` must be caught by
    the same guard as a direct constructor call -- this is the actual path a
    replayed MITgcm capture with `KPPuseDoubleDiff=1` would take (see
    MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py's
    `KPPuseDoubleDiff` -> `use_doublediff` parameter map)."""
    with pytest.raises(NotImplementedError, match="double diffusion"):
        KPPParameters(**{**_default_kwargs(), "use_doublediff": True})
    print("PASS test_use_doublediff_true_from_yaml_override_raises")


def _default_kwargs():
    """A couple of representative default kwargs, just enough to demonstrate
    the guard fires alongside other explicit settings (not an exhaustive
    from_yaml() reproduction)."""
    return {"Ricr": 0.3, "vonk": 0.4}


if __name__ == "__main__":
    test_use_doublediff_true_raises()
    test_use_doublediff_default_does_not_raise()
    test_exclude_doublediff_true_does_not_raise()
    test_use_doublediff_true_from_yaml_override_raises()
