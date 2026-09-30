# `global_ocean.cs32x15` + KPP: CONSTRUCTED run-input files (1DMIX-054)

**These namelists are constructed by this project. They are NOT a stock MITgcm experiment**: no
`data.kpp` / KPP-enabled `data.pkg` exists for `global_ocean.cs32x15` anywhere in the MITgcm tree.

## Read this first: pressure coordinates

This experiment runs in pressure coordinates (`buoyancyRelation='OCEANICP'`, `delR` in Pa, TEOS10,
model index k=1 at the sea floor with `rC` decreasing with k). MITgcm's `pkg/kpp` has **no**
pressure-coordinate handling (`grep -rn 'coordFac\|usingPCoords\|usingZCoords\|buoyancyRelation\|OCEANICP'
pkg/kpp/` returns nothing; `pkg/ggl90/ggl90_calc.F` converts with `coordFac = gravity*rhoConst`) and
has no guard against `useKPP` with pressure coordinates, so **MITgcm's own KPP evaluates pressures
in Pa as if they were metres**: KPP is not meaningful on this grid and this capture is a
**known-gap characterization, not a validation** (this project has no pressure-coordinate support,
permanently, 1DMIX-040). What was measured (details and tests: `KPP_port_validation/
KPP_VALIDATION_RESULTS.md`, `tests/test_kpp_mitgcm_validation_extended.py`):

* MITgcm's own KPP run **aborts at iteration 1** (`MON_SOLUTION: STOPPING CALCULATION`, potential
  temperature -1e13): `ghat` = 6.3e10 is applied to the tracers (`KPP_GHAT` is on in MITgcm's default
  `KPP_OPTIONS.h`). The capture therefore holds ONE time step (12 tiles, 1,621 wet columns, before the
  abort). With `KPP_GHAT` `#undef`'d (evidence-only rerun, not declared) the run completes 10 steps
  with the same unit-confused KPP output (background-only mixing, `hbl` = -2.5e5 in 99.3% of columns).
* The issue that requested this capture predicted that a port without pressure-coordinate handling
  might agree closely with MITgcm because both would make the same unit error. Measured: it does
  **not**. The port returns NaN in 91% of the interior interface cells of `visc_az`/`diff_kz`
  (the first floating-point error when one column is replayed is an overflow in `swfrac`'s
  `exp(-z/d)` with the Pa-valued depth) and its `hbl` differs from MITgcm's by a median 1.2e6.
  Only `ghat` is close (median abs diff 0, 87% of active cells within 1%, maximum 6.3275154945147095e10
  identical on both sides): **that agreement is shared unit-confused arithmetic, not port fidelity**,
  and the value MITgcm itself produces there is unphysical.

## Files

Companion compile side: `../kpp_code_validation/` (stock `code/` headers unmodified, `kpp` added to
the stock `packages.conf`, symlinked `kpp_calc.F`/`kpp_routines.F`, MITgcm's default `KPP_OPTIONS.h`).

| file | source | differences |
|---|---|---|
| `data` | `input.in_p/data` (the existing GGL90 capture's input) | `viscAr=1.030905162225000e+05`, `diffKrT=diffKrS=3.092715486675000e+03` uncommented (the experiment's own commented-out pressure-unit conversions of `1.E-3`/`3.E-5` m2/s by `(gravity*rhoConst)**2 = 1.0309e8`); `ivdc_kappa=0.` (required by `kpp_check.F:128-133`; `input.in_p` has 1.03e8) |
| `data.pkg` | `input.in_p/data.pkg` | `useKPP=.TRUE.` replaces `useGGL90=.TRUE.` |
| `data.kpp` | `global_oce_latlon/input_validation/data.kpp` | identical content, all MITgcm defaults |
| `data.diagnostics` | `input.in_p/data.diagnostics` | the five GGL90/IDEMIX diagnostic names (`GGL90TKE GGL90Kr GGL90Lmx IDEMIX_E IDEMIX_K`) removed from output stream 3: they do not exist with GGL90 off |

Deliberately no tuned KPP parameter is added.

## Reproduce

```bash
export MITGCM_ROOT=~/Projects/MITgcm
./assemble_run_dir.sh                            # creates verification/global_ocean.cs32x15/input.in_p_kpp
cd $MITGCM_ROOT/verification
./experiment_compile.sh global_ocean.cs32x15 -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_ocean_cs32x15/kpp_code_validation -build build_docker_kpp_054 -clean -j 8
./experiment_run_no_compile.sh global_ocean.cs32x15 input.in_p_kpp -build build_docker_kpp_054 -output output_kpp_cs32_054   # exits 1: MITgcm stops itself at iteration 1
cd <repo> && python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py $MITGCM_ROOT/verification/global_ocean.cs32x15/output_kpp_cs32_054/output.txt global_ocean.cs32x15
```
