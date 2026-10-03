# FABLE_FINDS — problems found in 1D_Mixing_Model while writing MITgcm_porting_wisdom

**Date:** 2026-10-02.
**Found by:** Claude (Fable 5.1) and its sub-agents, while distilling this
project into the reference library `../MITgcm_porting_wisdom`. The library's
authors and independent reviewers read this project's port, harnesses,
captures and records against the MITgcm source, and ran a few experiments.
**Compiled and re-checked by:** Claude (Opus 5.5), same day.

**State checked.** This project at `HEAD 336a85a` (2026-10-02 13:27) plus
the uncommitted working tree as it stood that afternoon (KPP files were being
edited for 1DMIX-075). MITgcm at `d861cd501` (`checkpoint69q` + 8). Line
numbers are from that working tree and will drift.

**What this file is.** A list of problems that were *not* in
`open_issues.md` or `closed_issues.md` when found. Nothing else in this
project was changed: no code, test, capture, ledger or document was edited,
and this file is not committed. None of the items has been through this
project's own gate.

**How to read the "Checked" line of each item.**

- **re-read today** — I opened the current files and the MITgcm source and
  the statement holds.
- **re-run today** — I ran it on the current tree.
- **library run** — measured by a library author or reviewer earlier today
  (often by two of them independently); I did not repeat it. The script is
  usually in `../MITgcm_porting_wisdom` (path given) or was not kept (said so).

Where the fuller write-up lives is given as "Detail", relative to
`../MITgcm_porting_wisdom/`.

---

## Summary

| ID | Problem | Kind | Measured effect |
| --- | --- | --- | --- |
| A1 | Convective-adjustment mask uses in-situ density at each level's own pressure; MITgcm uses a common reference level. Ledger 1DMIX-005 closed this wrongly | port defect | flags 0 of 19 interfaces where MITgcm's criterion flags 19 of 19 |
| A2 | Jerlov water type defaults to `"IB"`; MITgcm hard-codes type IA | port defect | max `hbl` difference 4.3e-2 m → 4.2e-3 m on one capture when corrected |
| A3 | `bosol` has the opposite sign convention to `bo` in the port's own forcing routine | port defect | −8.0e-8 vs +8.0e-8 m²/s³; masked in all tested paths |
| A4 | Physical constants are not single-sourced; an environment variable is set in 8 files and read by none | port defect | none on replays; scenario runs ignore the YAML |
| A5 | `sqrt_two = np.sqrt(2.0)` vs MITgcm's truncated literal | bit-identity | 3.5e-15 relative |
| A6 | `ustar**3` and `usta**3` where MITgcm multiplies (or gfortran expands to a product) | bit-identity | last bit differs in ~25% of values |
| A7 | Eight `np.sign` sites that differ from Fortran `SIGN` at exactly zero; at `bfsfc = 0` the port skips the Ekman/Monin–Obukhov limit | port defect | not measured |
| A8 | Linear-EOS branch of the GGL90 N² function has the wrong sign | port defect (dead code) | −2.2e-4 for a stable column |
| A9 | Friction-velocity floor differs from `KPP_FORCING_SURF` | port defect | 1.0e-5 vs 2.2e-5 m/s for a 10 m top cell |
| A10 | Port's `swfrac` lacks `SWFRAC`'s cut-off below 200 m | port defect | not measured |
| A11 | `compute_bl_mixing` returns 7 values on its `hbl == 0` path; the caller unpacks 5 | latent crash | not reached |
| A12 | `use_idemix` is accepted, never read, and not mapped from captures | silent option | none yet |
| A13 | Column driver applies `ivdc_kappa` together with KPP, a configuration MITgcm refuses | scope | none on replays |
| A14 | `epsln` and `phepsi` declared twice in `KPPParameters`; `to_dict()` methods never called | tidiness | none |
| A15 | `eos.py` docstring says `vermix` is on the reference-pressure EOS branch; it is not | wrong documentation of a physics assumption | see C8 |
| B1 | GGL90 standalone driver never sets `maskW`/`maskS`; `GGL90viscArU/V` have never been compared with MITgcm | verification gap | unmeasured |
| B2 | GGL90 driver forms `drC` differently from the model | latent last-bit trap | not observed |
| B3 | GGL90 driver build reads option headers from a leftover `code_validation` copy in the MITgcm tree | hidden dependency | — |
| B4 | Replay harnesses fall back silently to `gravity = 9.81`, `rhoConst = 1029.0` | harness defect | none on current captures |
| B5 | Replay harnesses find the wet range from `theta != 0.0` | harness defect | none observed |
| B6 | KPP replay turns any per-column exception into a NaN cell and continues | vacuity risk | — |
| B7 | Capture parser skips unrecognized lines silently | vacuity risk | — |
| B8 | Instrumentation is not thread-safe and prints no tile size or process offset | capture defect | threaded capture corrupt, MPI part-file parses as whole domain |
| B9 | KPP instrumentation still uses a level-1 land test and one literal `WRITE(6,…)` | capture defect | none observed |
| B10 | `compare_ggl90.py` does not check `input_uuid` and prints a fixed "Python port" banner | tooling | — |
| C1 | `lab_sea` captures use a single 20×16 tile; stock is 2×2 of 10×8, and the runs differ | reference data | `testreport` fails at 2 digits on the capture layout |
| C2 | The KPP `global_oce_latlon` capture is a constructed build, not a stock experiment | reference data | — |
| C3 | The constructed KPP capture on `global_ocean.90x40x15` ran horizontal smoothing with `OLx = 3` | reference data | unexamined |
| C4 | KPP capture variables `buoy_freq_sq`, `shear_sq`, `richardson`, `ghat` are mislabelled | capture metadata | values right, labels wrong |
| C5 | Captures lack `deltaT` (KPP), `eosType`, `selectP_inEOS_Zc`, tile sizes, MITgcm commit; attribute is `conventions`, not `Conventions` | capture metadata | — |
| C6 | GGL90 capture prints `dTtracerLev(1)`; the routine uses `dTtracerLev(kSrf)` | capture metadata | differs in pressure coordinates |
| C7 | The `vermix` GGL90 capture is a weak reference for the coefficient formula | reference data | 25 of 500 interior cells off a floor; a dropped-floor mutant passes |
| C8 | `vermix` uses `MDJWF` with `selectP_inEOS_Zc = 2`; the port has neither | scope / unexplained residual | 0.07–0.31% max rel (hypothesis) |
| C9 | `lab_sea` secondary input set `hb87` fails `testreport` at 5 digits in every build tried | unexplained | — |
| C10 | No capture holds the state after the implicit vertical solve | verification gap | — |
| C11 | One scenario file's provenance contradicts its own step count | scenario metadata | — |
| D1 | Ledger 1DMIX-005 ("false positive") is wrong | record | see A1 |
| D2 | Ledger 1DMIX-046 "preserved lesson" about COMMON blocks is false | record | — |
| D3 | Ledger 1DMIX-069 and the mods README call an upstream MITgcm bug a "transcription error" | record | — |
| D4 | "Issue 1" of `possible_kpp_bugs_in_mitgcm.md` is not an MITgcm bug | record | must not go upstream |
| D5 | The lookup-table extrapolation was reached by every real KPP capture, not only by a scenario | record | — |
| D6 | Root `README.md` status section still says KPP is validated and GGL90 not yet compared | record | — |
| D7 | `.tex` package and port descriptions contain factual errors | record | one wrong default (`dsfmax`) still present |
| D8 | `critical_lessons…md` still teaches `pressure = -depth` | record | — |
| D9 | Dead or always-skipping code presented as live | record | — |
| D10 | `kpp_calc.F.bak` is neither stock nor current | record | — |

Items withdrawn or already resolved by this project are in
[section E](#e-withdrawn-or-resolved-since).

---

## A. Defects in the Python port

### A1. Convective-adjustment mask compares the wrong densities

- **Where.** `Vertical_Mixing_Models/main/eos.py::compute_static_instability_mask`
  (line 468), called only from `main/unified_driver.py` (line 123) when
  `ivdc_kappa != 0`.
- **What the port does.** Computes in-situ density at every level with that
  level's own pressure and flags interface `k` where `rho[k-1] > rho[k]`.
- **What MITgcm does.** Both criteria compare two parcels at a *common*
  reference level. `calc_ivdc.F` tests `-sigmaR*gravitySign > 0`, and
  `sigmaR` is formed in `do_oceanic_phys.F` by `FIND_RHO_2D` on level `k-1`
  and level `k` with the same reference level. `convective_adjustment.F`
  calls `FIND_RHO_2D` twice with the same `k+deltaK`.
- **Why it matters.** In-situ density increases with depth through
  compression alone, so a column that is unstable in potential density is
  usually still "stable" in in-situ density. The port's mask hardly ever
  fires.
- **Evidence.** Column with T rising from 2.0 to 2.4 °C over 2 km at constant
  S (unstable everywhere in potential density): the port flags 0 of 19
  interfaces. A library reviewer's run found MITgcm's two criteria flag 19 of
  19 on such a column.
- **Checked.** Re-read today (port, `calc_ivdc.F`, `convective_adjustment.F`,
  `do_oceanic_phys.F`). Re-run today: 0 of 19.
- **Effect on published agreement.** None. The mask is used only by the
  free-running column driver, upstream of every comparison with MITgcm.
  Any scenario run with `--ivdc-kappa` is affected.
- **Ledger.** 1DMIX-005 examined exactly this and closed it as a false
  positive (`closed_issues.md` line 742: "also uses in-situ density on both
  sides — the sign test is density-type-independent"). It cited the two
  `FIND_RHO_2D` calls that share a reference level, and made no numerical
  check. See D1.
- **Fix.** Compare `rho(theta[k-1], salt[k-1], p_ref)` with
  `rho(theta[k], salt[k], p_ref)` at one reference level per interface, as
  `compute_ggl90_buoyancy_frequency_squared` already does for N².
- **Detail.** `Porting_MITgcm_to_Standalone_Python/02_pitfalls_and_gotchas.md`,
  `04_physical_consistency.md`.

### A2. Jerlov water type: port default `"IB"`, MITgcm hard-codes IA

- **Where.** `KPP/kpp_parameters.py` line 199 and
  `KPP/kpp_default_parameters.yaml` line 109 (`jerlov_water_type: "IB"`);
  used in `KPP/kpp_scheme_specific.py` (lines 152, 272, 333).
- **MITgcm.** `model/src/swfrac.F` line 92: `jwtype=2` (type IA), with the
  comment "Parameter jwtype is hardcoded to 2 for time being". There is no
  namelist entry, so no capture carries it and the "take every parameter from
  the capture" rule cannot catch it.
- **Evidence.** Replaying 2,000 steps of the 11,000-step single-column
  capture with IA instead of IB: median `hbl` difference 2.2e-5 m → 1.6e-6 m,
  maximum 4.3e-2 m → 4.2e-3 m.
- **Checked.** Both defaults re-read today. Replay: library run, reproduced
  independently by the Python-chapter reviewer; script not kept.
- **Effect on published agreement.** Affects every KPP full-model comparison
  wherever shortwave is non-zero. Measured on one capture only. Part of the
  `hbl` tail attributed to threshold sensitivity may be this.
- **Fix.** Default to `"IA"`; re-run every KPP full-model comparison.
- **Detail.** `Porting_MITgcm_to_Standalone_Python/02_pitfalls_and_gotchas.md`.

### A3. `bosol` uses the opposite sign convention to `bo`

- **Where.** `KPP/kpp_core_driver.py::_compute_surface_forcing` (line 621).
- **What.** `bo = -g*(ttalpha*temp_flux + …)/rho_surf` treats the heat flux
  as positive into the ocean. `bosol = g*ttalpha*sw_flux/rho_surf` is a
  literal copy of `kpp_forcing_surf.F` lines 236–238, which is correct only
  for MITgcm's `Qsw` (positive upward). With one convention for both
  arguments, one of the two terms has the wrong sign.
- **Evidence.** With the convention the scenarios use (positive = heating)
  and penetrating shortwave on, solar heating gives a negative
  (destabilizing) `bosol`: −8.0e-8 where +8.0e-8 m²/s³ is right at 10 °C.
- **Checked.** Code path re-read today. Number: library run (reviewer).
- **Effect.** Masked everywhere it was tested: the replay harness passes
  MITgcm-signed values, and all six scenarios leave penetration off. Any
  free-running use with `shortwave_heating` on is wrong.
- **Fix.** Pick one sign convention for `q_net` and `q_sw` at this boundary,
  state it in the docstring, and test it with a non-zero `q_sw`.
- **Detail.** `Porting_MITgcm_to_Standalone_Python/04_physical_consistency.md`.

### A4. Constants are not single-sourced

- **Where.** `main/run_scenarios.py::run_one` builds
  `KPPParameters.from_yaml(kpp_yaml)` without passing `gravity`, `rho_const`
  or `heat_capacity_cp` from `configuration_yamls/physical_parameters.yaml`.
  `KPPParameters` has its own defaults (lines 222–224).
- **Also.** `KPP_PHYSICAL_PARAMETERS_YAML` is assigned in eight Python files
  (`main/run_scenarios.py`, `main/run_experiment_example.py`,
  `tests/test_staggering.py`, `tests/test_full_scenario_validation.py`, three
  `scripts/analysis/*.py`, and
  `MITgcm_to_Python_port_verification/scripts/export_scenario_to_ggl90_driver.py`)
  and read by none.
- **Checked.** Re-read today; grep of the whole project.
- **Effect.** None today, because the YAML values equal the dataclass
  defaults, and replays take constants from the capture. Changing the YAML
  would change the driver's constants and not KPP's.
- **Fix.** Pass the physical constants into both parameter classes in
  `run_one`; delete the environment variable.

### A5. `sqrt_two` is not MITgcm's constant

- **Where.** `GGL90/ggl90_parameters.py` line 188: `sqrt_two = np.sqrt(2.0)`;
  used in `GGL90/ggl90_scheme_specific.py` line 142.
- **MITgcm.** `pkg/ggl90/GGL90.h` line 67:
  `PARAMETER ( SQRTTWO = 1.41421356237310D0 )`, a truncated literal that
  differs from √2 by 3.5e-15 relative.
- **Checked.** Both lines re-read today.
- **Effect.** The mixing length cannot be bit-identical where the
  `sqrt(2*TKE)/N` branch is active. Consistent in size with the remaining
  ~1e-13 m mixing-length residual, but that link was not tested by
  substitution (hypothesis).
- **Fix.** `sqrt_two: float = 1.41421356237310`.

### A6. Cubes written with `**3`

- **Where and what.**
  - `KPP/kpp_routines.py` line 207: `u3 = ustar[i]**3`. Fortran
    (`kpp_routines.F` line 1016): `u3 = ustar(i) * ustar(i) * ustar(i)`.
  - `KPP/kpp_scheme_specific.py` line 288:
    `hmonob = config.cmonob * ustar**3 / …`. Fortran (line 785):
    `cmonob * ustar(i)*ustar(i)*ustar(i)`.
  - `KPP/kpp_routines.py` lines 70, 81, 86 (lookup-table construction):
    `usta**3`. Fortran (`kpp_init_fixed.F` lines 139, 147, 152) also writes
    `usta**3`, which gfortran evaluates as the product `usta*usta*usta`.
- **Why.** For a Python float or NumPy scalar, `x**3` goes through `pow` and
  differs from `x*x*x` in the last bit for a fraction of values. (NumPy
  *arrays* with integer exponent 2 are exact; scalars are not.)
- **Evidence.** 25 of 112 stable-branch `wscale` test points differ in the
  last bit; gfortran agrees with the product form in 112 of 112. Tables built
  in Julia and NumPy differ in 2–4% of entries by at most 4.4e-16 relative;
  which one equals MITgcm's table is undetermined.
- **Checked.** All five port lines and the Fortran lines re-read today.
  Counts: library run
  (`Porting_MITgcm_to_Julia_Oceananigans/code_appendix/08_*`).
- **Effect.** Last-bit differences in the velocity scales, which the `hbl`
  threshold can amplify. Not separated in any statistic.
- **Fix.** Write `u*u*u`. Also check `(1.0 - ratio**2)**3` at lines 362 and
  367 against `kpp_routines.F` lines 1171–1179, which uses `ratio * ratio`
  and builds the cube in separate statements.

### A7. `np.sign` sites that differ from Fortran `SIGN` at zero

- **Where.** Eight sites remain:
  - `KPP/kpp_routines.py` 426, 427 (`KRi_range`; Fortran lines 1279–1281)
  - `KPP/kpp_scheme_specific.py` 165 (`stable_flag`; Fortran 577)
  - 282, 283 (`stable`, `bfsfc`; Fortran 765–766)
  - 342, 343 (`stable`, `bfsfc`; Fortran 902–903)
  - 356 (`casea`; Fortran 913)
- **What.** Fortran `p5 + SIGN(p5, x)` is 1 at `x = 0`;
  `0.5 + np.sign(x)*0.5` is 0.5. Fortran `SIGN(1,x)*MAX(phepsi,ABS(x))` is
  `+phepsi` at `x = 0`; `np.sign(x)*max(phepsi, abs(x))` is 0. The file
  already has the right idiom at line 488 (a comment there states this exact
  hazard), applied to one site only.
- **Consequence read from source.** At `bfsfc == 0` MITgcm gets
  `stable = 1`, `bfsfc = +phepsi > 0`, so it applies the Ekman and
  Monin–Obukhov limit to `hbl` (`kpp_routines.F` lines 781–790). The port
  gets `bfsfc = 0`, the test `bfsfc > 0.0` at line 286 is false, and the
  limit is skipped.
- **Checked.** Sites re-listed by grep today; Fortran lines re-read today.
- **Effect.** Not measured. Reached only at exactly zero buoyancy forcing
  (for example a start from rest with zero flux, or a synthetic scenario).
- **Fix.** `np.copysign(0.5, x)` and `np.copysign(1.0, x)` at all eight.

### A8. Linear-EOS N² has the wrong sign

- **Where.** `main/eos.py::compute_ggl90_buoyancy_frequency_squared`, `else`
  branch (lines 771–778).
- **What.** `depth` is negative downward, so `dz = depth[k] - depth[k-1] < 0`;
  for a stable column `rho[k-1] - rho[k] < 0`; the quotient is positive and
  `n_square = -(g/rho0)*drho_dz` is negative.
- **Evidence.** Stable column (T 20 → 10 °C, S = 35): `use_jmd95=True` gives
  +2.7e-4 s⁻²; `use_jmd95=False` gives −2.2e-4 s⁻².
- **Checked.** Re-run today.
- **Effect.** None today: the only caller (`GGL90/ggl90_core_driver.py` line
  442) hard-codes `use_jmd95=True`. Wrong the day it is switched on.
- **Fix.** Correct the sign or delete the branch; add a test.

### A9. Friction-velocity floor differs from MITgcm

- **Where.** `KPP/kpp_core_driver.py::_compute_surface_forcing`:
  `if tau_mag_sq < phepsi**2: ustar = sqrt(phepsi)`.
- **MITgcm.** `kpp_forcing_surf.F` lines 198–204: threshold
  `phepsi²·drF(1)²`, floor `SQRT(p5*phepsi*drF(1))`.
- **Numbers.** With `phepsi = 1e-10`: port floor 1.0e-5 m/s; MITgcm floor
  2.2e-5 m/s for a 10 m top cell. Both threshold and floor depend on the
  top-cell thickness in MITgcm and not in the port.
- **Checked.** Both re-read today.
- **Effect.** Not measured. Upstream of the replay harness (which passes
  MITgcm's `ustar`), so no comparison can see it; affects scenario runs at
  very weak wind.

### A10. `swfrac` has no 200 m cut-off

- **Where.** `KPP/kpp_shortwave.py`.
- **MITgcm.** `swfrac.F` line 99: below 200 m the fraction is set to exactly
  zero.
- **Checked.** Re-read today (no cut-off in the port file).
- **Effect.** Not measured; tiny but non-zero where MITgcm has an exact zero,
  which matters for bit-identity and for exact-zero tests below 200 m.

### A11. Inconsistent return shape in `compute_bl_mixing`

- **Where.** `KPP/kpp_scheme_specific.py`: the `hbl == 0.0` guard returns
  seven values (line 473); the normal path returns five, the last a tuple
  (line 669). The caller (`KPP/kpp_core_driver.py` line 550) unpacks five.
- **Checked.** Re-read today.
- **Effect.** If the guard is ever reached, the caller raises a `ValueError`
  on unpacking instead of returning zero mixing. In the replay harness that
  exception becomes a NaN cell (see B6).

### A12. `use_idemix` is silently ignored

- **Where.** `GGL90/ggl90_parameters.py` line 179. Accepted, printed, never
  read by the physics. No script maps a capture's `useIDEMIX` to it (grep of
  `MITgcm_to_Python_port_verification/scripts`).
- **Checked.** Re-read today. The sibling flag `calc_mean_vert_shear` has
  since been filed as 1DMIX-074; `use_idemix` is not in the ledger.
- **Effect.** A capture made with IDEMIX on would be replayed with no sign
  that the port lacks it.
- **Fix.** Raise `NotImplementedError` when `True`, and map the capture
  attribute so the harness refuses such a capture.

### A13. `ivdc_kappa` together with KPP

- **Where.** `main/unified_driver.py` applies `ivdc_kappa` on top of whatever
  scheme is active.
- **MITgcm.** `pkg/kpp/kpp_check.F` lines 128–129 stops the model when
  `cAdjFreq != 0` or `ivdc_kappa != 0` with KPP. (`pp81_check.F` does the
  same; `ggl90_check.F` only prints a notice.)
- **Checked.** Re-read today.
- **Effect.** The port can run a configuration MITgcm refuses, so there is no
  reference for it. Combined with A1, the step also does not do what MITgcm's
  does.

### A14. Minor

- `KPPParameters` declares `epsln` and `phepsi` twice (lines 87–88 and
  227–228). Same values today; the second silently wins.
- `KPPOutput.to_dict()` and `GGL90Output.to_dict()` are never called (grep).
- `GGL90/ggl90_default_parameters.yaml` sets `alpha: 10.0` on purpose
  (MITgcm's default is 1.0, `ggl90_readparms.F` line 110), and says so. But
  `docs/GGL90/GGL90_port_description.tex` line 566 still says
  "(default: 1.0)". Any caller relying on the port's defaults does not
  reproduce MITgcm's.

### A15. `eos.py` module docstring is wrong about `vermix`

- **Where.** `main/eos.py` lines 34–37 list `vermix` among the experiments on
  the "non-iterative reference-pressure branch, `selectP_inEOS_Zc<=1`".
- **MITgcm.** `set_parms.F` lines 275–281 set `selectP_inEOS_Zc = 2` for
  `JMD95P`, `UNESCO`, `MDJWF` and `TEOS10`, and 0 otherwise. `vermix` uses
  `eosType='MDJWF'` (`verification/vermix/input/data` line 24), so it runs
  with the model's own hydrostatic pressure in the EOS. A library author
  confirmed `selectP_inEOS_Zc = 2` in the `vermix` STDOUT echo.
- **Checked.** Docstring, `set_parms.F` and the `data` file re-read today.
- **Effect.** See C8.

---

## B. Verification harnesses, standalone drivers and instrumentation

### B1. `GGL90viscArU` / `GGL90viscArV` have never been verified

- **Where.** `mitgcm_verification_mods/ggl90_standalone_driver/ggl90_standalone_main.F`
  never assigns `maskW` or `maskS` (no occurrence in the file).
  `ggl90_calc.F` forms the U- and V-point viscosities with
  `_maskW(i,j,k-1)*_maskW(i,j,k)` (lines 1042, 1065), so in the driver they
  fall back to the background value.
- **Why nobody noticed.** Those two arrays are neither captured nor compared
  anywhere.
- **Checked.** Re-read today.
- **Effect.** One of GGL90's outputs to the model has no verification at all,
  in the full-model leg or the driver leg.
- **Fix.** Capture them; set the masks in the driver; compare.

### B2. The GGL90 driver forms `drC` differently from the model

- **Where.** Driver lines 153–161: `drC(k) = rC(k-1) - rC(k)`. The model
  (`ini_vertical_grid.F`) uses `0.5*(delR(k-1)+delR(k))`.
- **Checked.** Driver re-read today.
- **Effect.** Algebraically equal, not guaranteed bit-equal. Not observed to
  matter (the driver reproduced the full-model `vermix` capture bit for bit
  on 2,080 of 2,080 values in a library run), so this is a latent trap for
  other grids.

### B3. Driver build depends on a leftover directory in the MITgcm tree

- **Where.** `ggl90_standalone_driver/build_and_run.sh` lines 28–31:
  `PKGCONFIG_DIR="$VERMIX_DIR/build_docker_ggl90_1dmix024"`,
  `CPPOPTS_DIR="$VERMIX_DIR/code_validation"`.
- **What.** `verification/<exp>/code_validation` is whatever the last
  `experiment_compile.sh -mods` left there, not the tree in this repository.
  A later `-mods` build of another variant changes what the driver compiles
  against. The script also writes its build products into the tracked driver
  directory, and a library author needed an extra `-Ipkg/generic_advdiff` to
  build it out of tree.
- **Checked.** Script re-read today.
- **Fix.** Point at `mitgcm_verification_mods/vermix/code_validation` in this
  repository.

### B4. Silent fallbacks for physical constants

- **Where.** `scripts/run_ggl90_from_netcdf_input.py` lines 203–206:
  `attrs.get('gravity', 9.81)`, `attrs.get('rhoConst', 1029.0)`,
  `attrs.get('viscAz', 0.0)`, `attrs.get('diffKzS', 0.0)`.
- **Checked.** Re-read today.
- **Effect.** A capture missing an attribute is replayed with a default and
  no message. This is the failure the "constants come from the capture" rule
  exists to prevent.
- **Fix.** Index the attribute (`attrs['gravity']`) so absence raises.

### B5. Wet range found from a value

- **Where.** `run_ggl90_from_netcdf_input.py` line 125 and
  `run_kpp_from_netcdf_input.py` line 509: `wet = np.flatnonzero(theta != 0.0)`.
- **Checked.** Re-read today.
- **Effect.** A wet cell at exactly 0 °C is treated as land. Use the captured
  mask or `hFacC`.

### B6. Per-column exceptions become NaN cells

- **Where.** `run_kpp_from_netcdf_input.py` lines 1047–1050
  (`except Exception … continue`) and the worker's error dictionary. The
  script's own comment at line 833 describes the hazard; the geometry guard
  added for 1DMIX-072 covers one cause only.
- **Checked.** Re-read today.
- **Effect.** Any port exception (A11, for instance) is reported as missing
  data, not as a failure. Tests that mask NaN then compare fewer cells
  without saying so.
- **Fix.** Count failures and fail the run when the count is non-zero.

### B7. Parser skips unrecognized lines

- **Where.** `scripts/capture_stream.py` (`continue` at lines 182–212) and the
  per-package line grammars.
- **Effect.** A truncated or corrupted line is dropped without a count.
- **Checked.** Read today; behaviour described by the library's V&V 01–07
  author and reviewer.
- **Fix.** Count dropped tagged lines and report them; fail above zero.

### B8. Instrumentation under threads and MPI

- **What.** The instrumentation writes to the standard message unit with no
  lock and prints no tile size, tile count or global offset. The parser
  infers tile size from the largest index seen.
- **Evidence (library run on `lab_sea`, 9 steps, five layouts).**
  - 2 MPI processes: bitwise identical to serial in all 163,350 records once
    the two `STDOUT.000N` files are merged with the right offset. Both files
    label their tiles `BI=1`, and the parser accepts one file alone as a
    complete 10×16 domain.
  - 2 threads: the capture is corrupt (6,012 conflicting keys, 68,581 records
    missing) and still parses without error.
- **Checked.** Library run, re-run by the V&V 13–17 reviewer from the saved
  captures. Script:
  `Verification_and_Validation/code_appendix/16_compare_tile_layouts.py`.
- **Fix.** Print `sNx`, `sNy`, `nSx`, `nSy`, `myXGlobalLo`, `myYGlobalLo` in
  the header; refuse to run the instrumented build with `nTx*nTy > 1`.

### B9. Remnants in `kpp_mods/kpp_calc.F`

- Line 1258 still uses the level-1 land test
  (`IF ( maskC(i,j,1,bi,bj) .EQ. 0. ) CYCLE`). The GGL90 instrumentation was
  changed to test all levels because ice-shelf columns are dry at the top;
  KPP's was not.
- Line 906 has a literal `WRITE(6,…)` where every other write uses
  `standardMessageUnit`.
- **Checked.** Re-read today.

### B10. `compare_ggl90.py`

- Prints a fixed banner "MITgcm vs. Python port" whatever it is given (line
  54), does not check that the two files' `input_uuid` match, and fails when
  a variable is absent.
- **Checked.** Banner re-read today; the rest reported by the Julia-chapter
  author and reviewer, who fed it another code's output.

---

## C. Reference data (captures and scenarios)

### C1. The `lab_sea` captures are not the stock experiment

- **Where.** `mitgcm_verification_mods/lab_sea/code_validation/SIZE.h` and
  `…/ggl90_code_validation/SIZE.h`: `sNx=20, sNy=16, nSx=1, nSy=1`. Stock
  `MITgcm/verification/lab_sea/code/SIZE.h`: `sNx=10, sNy=8, nSx=2, nSy=2`.
- **Why it matters.** The sea-ice dynamics (LSR) solver works tile by tile and
  converges differently on one tile, so surface forcing differs from the
  first step.
- **Evidence (library run).** `testreport` on the single-tile build fails with
  2 matching digits. 134 of 1,350 forcing records are identical between
  layouts, maximum relative difference 1.67. With the solver's full-domain
  option compiled into both layouts the largest difference falls to 1.5e-8.
- **Checked.** Both `SIZE.h` files re-read today. Runs: library run, re-run by
  the reviewer from saved captures.
- **Effect.** Single-step replay against these captures remains valid (the
  port is fed what MITgcm computed). They cannot be called "the `lab_sea`
  verification experiment", and nobody had run `testreport` on the capture
  build.
- **Rule.** Capture in the stock tile layout, or run `testreport` on the
  changed one first and record the result.

### C2. The KPP `global_oce_latlon` capture is a constructed build

- **What.** Stock `verification/global_oce_latlon/code/packages.conf` does not
  compile KPP. The capture was built from a forward variant assembled out of
  the former `code_oad` / `input_oad.kpp` configuration
  (`mitgcm_verification_mods/global_oce_latlon/input_validation/README.md`),
  which is no longer in the pinned MITgcm tree (it now has `code_ad` and
  `code_tap` only). Its `KPP_OPTIONS.h` undefines `KPP_GHAT` and all
  smoothing.
- **Checked.** README, `packages.conf` and the options header re-read today.
- **Effect.** It should carry the same CONSTRUCTED label and per-setting
  justification as the other constructed experiments. Statements that this
  capture exercises a stock MITgcm KPP experiment are wrong.

### C3. Horizontal smoothing with a 3-point overlap

- **What.** The constructed KPP capture on `global_ocean.90x40x15`
  (`mitgcm_verification_mods/global_ocean_90x40x15/kpp_code_validation/`) has
  no `KPP_OPTIONS.h`, so it uses the stock one, where `KPP_SMOOTH_SHSQ` and
  `KPP_SMOOTH_DBLOC` are defined. Its `SIZE.h` has `OLx = 3`. The capture's
  own attributes confirm `smooth_shsq = 1`, `smooth_dbloc = 1`.
- **MITgcm.** `kpp_check.F` documents that smoothing needs `OLx = OLy = 4`,
  but the test is compiled only under `KPP_REACTIVATE_OL4`, which is defined
  nowhere in the tracked tree, so the model does not stop.
- **Checked.** All re-read today; attributes read from the capture file.
- **Effect.** Unexamined. Columns near tile edges may have been smoothed with
  halo values MITgcm's own comment says are not valid. This is a candidate
  contributor to the tile-edge and multi-column residuals.
- **Next step.** Rebuild with `OLx = OLy = 4` and compare the two captures at
  tile-edge columns.

### C4. Mislabelled KPP capture variables

- **Where.** `scripts/parse_mitgcm_split.py` variable table (lines 607–631).
- **What.**
  - `buoy_freq_sq`: labelled "Buoyancy frequency squared (N²)", `1/s^2`. It
    holds `dbloc(k)`, a buoyancy *difference* between adjacent levels, in
    m/s², on the bottom face of cell `k`.
  - `shear_sq`: labelled "Vertical shear squared", `1/s^2`. It holds
    `shsq(k)`, a squared velocity *difference*, in m²/s².
  - `richardson`: labelled "Gradient Richardson number (Ri = N²/S²)",
    dimensionless. It is `dbloc/shsq`, in 1/m, a quantity that exists nowhere
    in MITgcm (`Ri_iwmix` uses `dblocSm*Δz/MAX(shsq, phepsi)`). The parser's
    own later comment (line 661) already says it is `dbloc/shsq`.
  - `ghat`: declared on `('x','y','z')` with `cell_location: center`. It is a
    bottom-face array.
- **Checked.** Parser table re-read today; instrumented writes read by two
  library authors.
- **Effect.** The values are right and the port is fed what `KPPMIX`
  receives. Anyone who trusts the metadata is off by a layer thickness. A
  library harness that compared Oceananigans' N² with `buoy_freq_sq` hit
  exactly this.
- **Fix.** Rename to `dbloc`, `shsq`; correct units and locations; drop or
  rename `richardson`.

### C5. Missing capture attributes

- Read from two KPP input files today (`…1D_10_kppmix_extend_rawflux_fix.nc`,
  `…global_oce_latlon_720.nc`, 220 attributes each): no `deltaT`, no
  `eosType`, no `selectP_inEOS_Zc`, no `useRealFreshWaterFlux`, no tile sizes,
  no MITgcm commit. The global attribute is `conventions`, where CF requires
  `Conventions`.
- **Effect.** The EOS a capture ran with, its time step, and the branch of
  `external_forcing_surf.F` that formed the salt flux cannot be read from the
  file; a replay has to trust the experiment's `data` file. `build_info.txt`
  and `run_info.txt` (written by `MITgcm_verification_docker`) record neither
  the MITgcm commit nor a hash of the mods tree.

### C6. GGL90 capture prints the wrong time step

- **Where.** `ggl90_mods/ggl90_calc.F` line 254 uses
  `deltaTloc = dTtracerLev(kSrf)`; line 1395 prints
  `'PARAM_deltaT=',dTtracerLev(1)`. The file's own comment at line 1391 notes
  the difference.
- **Checked.** Re-read today.
- **Effect.** Equal in z-coordinates with a uniform tracer time step. They
  differ in a pressure-coordinate run or with level-dependent `dTtracerLev`.

### C7. `vermix` is a weak reference for the GGL90 coefficient formula

- **Evidence (library run).** On the `vermix_20` capture only 25 of 500
  interior cells are off a background floor. A translation of the coefficient
  formula matched MITgcm in 520 of 520 cells, and so did a mutant with the
  TKE floor dropped.
- **Checked.** Library run, re-run by the reviewer
  (`Porting_MITgcm_to_Julia_Oceananigans/code_appendix/08_python_to_julia_kernels.jl`).
- **Effect.** "520 of 520 cells agree" on this capture says little about the
  formula. A test on it needs a non-vacuity assertion (how many cells are off
  the floor).
- **Related.** `test_vermix_clean_bit_level`
  (`tests/test_ggl90_mitgcm_validation.py` line 140) asserts only
  `max_rel < 0.01`; "bit-level" in its name is a misnomer.

### C8. `vermix`: `MDJWF` and `selectP_inEOS_Zc = 2`

- **What.** `vermix` runs `eosType='MDJWF'`, and for that EOS MITgcm takes the
  EOS pressure from the model's own hydrostatic pressure. The port implements
  JMD95 with a depth-derived pressure only. The parser text already notes the
  EOS mismatch (`parse_mitgcm_ggl90_split.py` line 236) and the harness feeds
  the captured `sigmaR` to avoid it.
- **Open.** The GGL90 results document gives no cause for the 0.07–0.31%
  maximum relative differences on `vermix`, while the other single-column
  capture is at roundoff. **Hypothesis:** some remaining density-dependent
  quantity in the replay is still computed with JMD95 at depth-derived
  pressure. Not tested.
- **Checked.** `data` file and parser text re-read today.

### C9. `lab_sea` `hb87` fails `testreport`

- **Evidence (library run).** The secondary input set `input.hb87` matches the
  reference output to only 5 digits in every build tried, including the stock
  2×2 layout at `-O0`. The primary set passes at 16 digits in the stock
  layout.
- **Not separated.** All those builds used the instrumented sources. No run
  with uninstrumented sources was made, so this may be the platform, the
  toolchain, or the instrumentation.
- **Next step.** Run `testreport` on stock `lab_sea` with no `-mods`.

### C10. No capture after the implicit vertical solve

- No capture holds the state after `IMPLDIFF`. The port's diffusion operator,
  its placement of the non-local term, and the unified driver's time stepping
  have therefore never been compared with MITgcm; only the coefficients have.

### C11. Scenario provenance

- `simulations/scenarios/scenario_combined_storm_time_integration.yaml`:
  `duration_hours: 24.0`, `dt_seconds: 3600.0`,
  `n_steps_formula: round(duration_hours*3600/dt_seconds)` (= 24), and
  `n_steps: 72`.
- **Checked.** Re-read today. A library checker
  (`Verification_and_Validation/code_appendix/08_check_scenario.py`) flagged
  stale provenance in two of the six scenarios.

---

## D. Records: ledger, reports, documents

### D1. 1DMIX-005 was closed wrongly

`closed_issues.md` line 742 concludes MITgcm "also uses in-situ density on
both sides". The two `FIND_RHO_2D` calls it cites pass the *same* reference
level, so both densities are referenced to one pressure. See A1. The entry
should be reopened or superseded with a forward pointer. `docs/model_contract.md`
should be checked for the same statement.

### D2. 1DMIX-046: the "preserved lesson" is false

`closed_issues.md` line 1440 says COMMON-block variables assigned in a
wrapper's main program are not visible to subroutines, and that the later
drivers avoid this by using the `genmake2` build. Fortran COMMON storage is
global. `ggl90_standalone_main.F` assigns COMMON arrays in its main program,
is built by its own script without `genmake2`, and reproduces the full model
bit for bit. The real cause of the abandoned wrapper's failure was never
established.

### D3. The loop bound was an upstream MITgcm bug, not a transcription error

- `mitgcm_verification_mods/README.md` line 109 and ledger 1DMIX-069 describe
  `DO i=jMin,jMax` in the instrumented `ggl90_calc.F` as a transcription error.
- MITgcm history (`git log -S'DO i=jMin,jMax' -- pkg/ggl90/ggl90_calc.F`):
  introduced by `f18a893d4` (2022-08-02, "ggl90 with shelfice (#597)") and
  fixed by `09a9aa1d4` (2026-08-10, "Fix loop limits in
  pkg/ggl90/ggl90_calc.F").
- A library reviewer diffed the pre-correction instrumented file against the
  older upstream source: zero changed stock lines.
- **What really happened.** The instrumented file was derived from an older
  MITgcm and compiled into a newer checkout. `-mods` replaces whole files, so
  the upstream fix was silently dropped. Captures built between the checkout
  update and 2026-09-30 ran a hybrid (new model, old package file); the bug
  was dormant in all of them because the tiles were square.
- **Rule.** Record the MITgcm commit each instrumented file was derived from,
  and re-derive it whenever the checkout moves.
- **Checked.** `git log` re-run today; README line re-read today.

### D4. "Issue 1" of `possible_kpp_bugs_in_mitgcm.md` is not a bug

- The report's Issue 1 ("Missing hbl Regularization in BLMIX") says `hbl` can
  reach a division unregularized.
- `kpp_routines.F` line 799 (end of `bldepth`):
  `hbl(i) = MAX(hbl(i),minKPPhbl)`. `kpp_init_fixed.F` lines 162–163 set
  `minKPPhbl = -rC(1)` when it is left unset. `KPPMIX` changes nothing between
  `bldepth` and `blmix`.
- The two real routes to a non-positive `hbl` are a user setting
  `minKPPhbl = 0`, and pressure coordinates (where `-rC(1)` is negative).
- **Do not send Issue 1 upstream.** Issue 2 (the `wscale` lookup-table
  extrapolation, with its fix sitting commented out) stands. The ledger
  records no upstream submission of either.
- **Checked.** All three source lines re-read today.

### D5. The lookup-table extrapolation and real captures

The received account is that only the `combined_storm` scenario reached the
extrapolating branch. The project's own final resolutions (1DMIX-056, -057)
show all four real KPP captures entered it, at 1.2% to 12.9% of evaluations,
and two other scenarios entered it with no measurable effect. The
disagreement was in the real captures all along and had been attributed to
threshold sensitivity.

### D6. Root `README.md` status is stale

Lines 21–35 still say "KPP port: validated against MITgcm", attribute the
outliers to floating-point behaviour near the critical Richardson number, and
say the GGL90 port is "not yet put through the MITgcm capture-and-compare
pipeline". All three were superseded weeks ago. Re-read today.

### D7. Errors in the `.tex` descriptions

Found by the library's Documentation author and reviewer, who opened each
against the MITgcm source. The descriptions are useful for their outline and
unreliable as fact sources.

- `docs/KPP/KPP_package_description.tex` line 659 gives `dsfmax` as 10⁻³.
  MITgcm: `dsfmax = 10. _d -3`, which is 1e-2 (`kpp_readparms.F` line 143);
  the port has 1e-2. An archived review "corrected" the right value to the
  wrong one by misreading the literal. **Re-read today.**
- `docs/GGL90/GGL90_package_description.tex` has 473 lines after
  `\end{document}` (line 4067 of 4540). **Re-read today.**
- Not re-read today, as recorded by the reviewer:
  - eight duplicated labels in the GGL90 package description;
  - a listing captioned as verified against the real MITgcm source that cites
    the wrong line range, drops a three-line adjoint-directive block and adds
    a comment that is not in the source;
  - invented names in the KPP port description (`KPPRicr`, `KPPVtc`, a
    `zref = 10.0 m` parameter);
  - a reference to a non-existent `main/convective_adjustment.py`;
  - stale Python line ranges;
  - salt plume listed as excluded while `kpp_salt_plume.py` exists.
- Detail: `Documentation/02_documenting_the_original_parameterization.md`
  (error catalogue, 16 classes).

### D8. `critical_lessons_fortran_to_python_porting.md` teaches a superseded rule

Lines 254–277 conclude `pressure = -depth` (1 dbar per metre). 1DMIX-039
established that MITgcm's EOS pressure is `rhoConst*gravity*|z|*1e-5` bar,
0.8–1.9% away from that. Re-read today.

### D9. Dead or always-skipping code that looks live

- `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py` points
  at `mitgcm_instrumentation/lab_sea_kpp_data.h5`, a tree that no longer
  exists, so it always skips. It is the only test asserting `rtol=1e-12`.
- `Vertical_Mixing_Models/generate_extreme_scenario_yamls.py` documents and
  imports `KPP_PY/extreme_scenarios.py`, which does not exist.
- Both re-read today.

### D10. `kpp_mods/kpp_calc.F.bak`

It differs from stock `pkg/kpp/kpp_calc.F` (434 differing lines) and from the
current instrumented file. It is an earlier instrumented version, not a copy
of stock as one survey described it. Compared today with `cmp` and `diff`.

### D11. Smaller record items (not re-read today)

Reported by the library's worked-example and V&V authors:

- Five capture recipes are marked INFERRED in the two `CAPTURES.md` files, and
  17 capture files were read by tests but not declared as external inputs.
- Evidence receipts cited by hash in the ledger lived under the git-ignored
  `devel-loop/loop_state/` and were lost in the host move; the same applies to
  several decisive scratch scripts.
- A mutation-check script in scratch (`mutants.py`) has one mutant that
  changes sign as well as operation order, so its detection proves nothing
  about ordering; and `-(g/rhoConst)` versus `g*(-1)*(1/rhoConst)` is an
  equivalent mutant at the round constants used. Bit-order tests should
  include random constants.
- The two validation result documents contained about 30 issue-id citations
  each, against the stated acceptance criterion of none.
- `esx/project_profile.md` excludes multi-column configurations while the
  suite replays multi-column captures.
- `mitgcm_verification_mods/TAF_*.md` are stale (paths from the previous host;
  they predate the toolchain's `-adm`/`-tlm` support).

---

## E. Withdrawn or resolved since

- **Withdrawn: EOS of the `global_oce_latlon` capture.** The library draft
  said it was unverified, because stock `input/data` selects `POLY3` and the
  port has only JMD95. The capture's own
  `global_oce_latlon/input_validation/data` sets `eosType = 'JMD95Z'` (read
  today). No problem, beyond the capture file not carrying `eosType` (C5).
- **Resolved here today: column-local velocities in multi-column replays.**
  The library recorded this as open; 1DMIX-071 was closed at 13:25 (`1fcf0cd`).
  Every shear-dependent residual quoted before that closure should be read as
  superseded.
- **Resolved here today: GGL90 on pressure-coordinate input** (1DMIX-073,
  `cbbbed2`).
- **Now in the ledger:** `calc_mean_vert_shear` accepted but never read
  (1DMIX-074).
- **Not a defect:** gfortran's `MAX`/`MIN` with a NaN argument. Two library
  authors reported different behaviour; a third test showed it depends on
  optimization level and on how the NaN arose. No port code depends on it as
  far as was found.

---

## F. Suggested order of work

1. **A2 (Jerlov).** One-line change with a measured tenfold effect; then
   re-run every KPP full-model comparison. Several open KPP residuals
   (1DMIX-075, -076) should be re-measured after it.
2. **A1 with D1.** Fix the mask; reopen 1DMIX-005.
3. **A3, A7, A9, A10.** The port's own forcing path and zero-forcing
   behaviour. Each needs a test that is not degenerate (non-zero `q_sw`,
   exactly zero `bfsfc`, weak wind, depth below 200 m).
4. **A5, A6.** One-line changes toward bit-identity; then check whether the
   GGL90 mixing length and the KPP stable branch reach exact equality.
5. **B1.** Capture and compare `GGL90viscArU/V`.
6. **B4, B6, B7.** Make silent fallbacks and swallowed exceptions fail.
7. **C1, C3.** Recapture `lab_sea` in the stock layout, and
   `global_ocean.90x40x15` KPP with `OLx = OLy = 4`; or state the layout with
   every number.
8. **C4, C5, C6.** Correct capture metadata at the next recapture.
9. **D2–D8.** Correct the records, each with a forward pointer from the old
   entry so the wrong conclusion is not quoted again. Do not send Issue 1
   upstream (D4).

What these have in common: almost every port defect sits where no comparison
could see it. A1, A3, A4, A9 and A13 are upstream of every harness boundary.
A2 is a constant MITgcm does not expose. A5 and A6 are below the print
precision that hid them until the 17-digit recapture. A7 and A8 are in
branches no reference enters. A green test suite said nothing about any of
them. A periodic whole-port read against the Fortran, by someone who did not
write the port, is what found them.

---

## Where the detail is

All paths relative to `../MITgcm_porting_wisdom/`.

| Topic | File |
| --- | --- |
| The list as first recorded, with what each reviewer re-checked | `Other_Wisdom/03_worked_example_vertical_mixing.md`, "Found while writing this reference" and "What remains open or unexplained" |
| Port defects with code excerpts | `Porting_MITgcm_to_Standalone_Python/01_language_differences.md`, `02_pitfalls_and_gotchas.md`, `04_physical_consistency.md`, `06_compile_and_runtime_switches.md` |
| MITgcm conventions each defect is measured against | `MITgcm_background/03_physics_conventions.md` |
| Capture schema and the mislabelled variables | `Verification_and_Validation/04_io_schema_and_netcdf.md` |
| Standalone drivers | `Verification_and_Validation/05_standalone_mitgcm_drivers.md` |
| Stale instrumented copy; instrumentation rules | `Verification_and_Validation/06_instrumenting_mitgcm.md`, `17_identifying_mitgcm_bugs.md` |
| Tile layout, MPI, threads, `-O3`, `hb87` | `Verification_and_Validation/15_platform_specific_testing.md`, `16_parallel_testing.md` |
| Bit-identity measurements (`**3`, `sqrt_two`, powers) | `Verification_and_Validation/12_bit_identical_gold_standard.md` |
| Errors in the `.tex` descriptions; ledger reversals | `Documentation/02_documenting_the_original_parameterization.md`, `04_recording_issues_and_evidence.md` |
| Every open question, with how to answer it | `Other_Wisdom/07_open_questions.md` (groups D and E) |
