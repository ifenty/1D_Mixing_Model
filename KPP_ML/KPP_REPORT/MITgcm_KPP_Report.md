# MITgcm KPP Package Report

Date: 2026-07-15

Repository examined: `/Users/ifenty/git_repo_others/MITgcm`

Package examined: `pkg/kpp`

## 1. Purpose and Scope

The MITgcm `pkg/kpp` package implements the K-Profile Parameterization (KPP) for vertical mixing in the ocean column. In MITgcm, KPP is not a standalone tracer update scheme. Its main job is to compute vertical mixing coefficients and a nonlocal transport coefficient that are then consumed by the model's momentum and tracer operators.

At a high level, the package does four things:

1. Computes interior vertical mixing from shear instability, static instability, and a constant internal-wave background.
2. Diagnoses a boundary-layer depth `KPPhbl` from a bulk Richardson number criterion.
3. Computes enhanced boundary-layer viscosity and diffusivity profiles inside the KPP boundary layer.
4. Optionally computes a nonlocal transport term `KPPghat` for unstable convective forcing.

The package is documented in `doc/phys_pkgs/kpp.rst`, but the operational behavior is controlled by the Fortran sources in `pkg/kpp`, especially `kpp_calc.F`, `kpp_routines.F`, `kpp_forcing_surf.F`, `kpp_readparms.F`, `KPP.h`, and `KPP_PARAMS.h`.

## 2. What the Package Produces

The package's externally visible outputs are the shared arrays declared in `pkg/kpp/KPP.h`:

- `KPPviscAz(i,j,k,bi,bj)`: vertical eddy viscosity on tracer points, units `m^2/s`
- `KPPdiffKzT(i,j,k,bi,bj)`: vertical diffusivity for temperature, units `m^2/s`
- `KPPdiffKzS(i,j,k,bi,bj)`: vertical diffusivity for salinity and passive tracers, units `m^2/s`
- `KPPghat(i,j,k,bi,bj)`: nonlocal transport coefficient, units `s/m^2`
- `KPPhbl(i,j,bi,bj)`: diagnosed KPP boundary-layer depth, units `m`
- `KPPfrac(i,j,bi,bj)`: fraction of shortwave flux heating the mixing layer, dimensionless
- `KPPplumefrac(i,j,bi,bj)`: fraction of salt-plume flux penetrating the mixing layer, dimensionless, only when `ALLOW_SALT_PLUME` is enabled

These outputs are not final tendencies themselves. They are later inserted into the model through:

- `model/src/calc_viscosity.F` via `KPP_CALC_VISC`
- `model/src/calc_3d_diffusivity.F` via `KPP_CALC_DIFF_T`, `KPP_CALC_DIFF_S`, and `KPP_CALC_DIFF_Ptr`
- tracer nonlocal flux terms via `KPP_TRANSPORT_T`, `KPP_TRANSPORT_S`, and `KPP_TRANSPORT_PTR`
- diagnostics and snapshot output via `KPP_OUTPUT`

## 3. Required Activation and Configuration

### 3.1 Compile-time activation

The package must be compiled in by enabling `kpp` in MITgcm package configuration. The user-facing documentation states this can be done through `packages.conf` or `genmake2` options.

Important compile-time controls are in `pkg/kpp/KPP_OPTIONS.h`. The main ones affecting behavior are:

- `KPP_GHAT`: enables the nonlocal transport coefficient and associated flux terms
- `KPP_SMOOTH_SHSQ`: smooths local vertical shear squared
- `KPP_SMOOTH_DBLOC`: smooths local buoyancy jump `dbloc`
- `KPP_SMOOTH_DENS`: smooths density-derived fields
- `KPP_SMOOTH_VISC`: smooths the final viscosity field horizontally
- `KPP_SMOOTH_DIFF`: smooths the final diffusivity fields horizontally
- `EXCLUDE_KPP_SHEAR_MIX`: removes shear-instability contribution in the interior-mixing calculation
- `EXCLUDE_KPP_DOUBLEDIFF`: removes double-diffusive enhancement code
- `KPP_ESTIMATE_UREF`: changes how the surface reference velocity used in `dVsq` is estimated

Related compile-time dependencies and interactions:

- `SHORTWAVE_HEATING` is needed if penetrating shortwave radiation is to affect KPP.
- `ALLOW_SALT_PLUME` adds plume buoyancy forcing and salt-plume flux partitioning.
- `ALLOW_GMREDI` matters for the option `KPP_ghatUseTotalDiffus`, where the nonlocal term can use total diffusivity including GM/Redi vertical diffusivity.
- `ALLOW_PTRACERS` enables KPP support for passive tracers.
- `ALLOW_OFFLINE` changes how some KPP fields can be loaded and used in offline mode.

### 3.2 Run-time activation

The package only runs when `useKPP = .TRUE.` in `data.pkg`.

The documentation and code also require:

- `implicitViscosity = .TRUE.`
- `implicitDiffusion = .TRUE.`

These are required because KPP supplies vertical mixing coefficients that are intended to be used by the model's implicit vertical mixing operators.

### 3.3 Run-time parameter file

Runtime parameters are read from `data.kpp` in `KPP_READPARMS`, namelist `KPP_PARM01`.

The principal user-controlled parameters are:

#### Scheduling and I/O

- `kpp_freq`: recomputation interval for KPP fields
- `kpp_dumpFreq`: dump interval for KPP snapshot fields
- `KPPwriteState`: if true, write snapshot files or MNC output

#### Behavior flags

- `KPP_ghatUseTotalDiffus`: if true, use total vertical diffusivity rather than only KPP diffusivity in the nonlocal term
- `KPPuseDoubleDiff`: if true, add double-diffusive contributions to background tracer diffusivities before the KPP column solve
- `LimitHblStable`: if true, limit the depth of `hbl` in stable forcing conditions
- `KPPuseSWfrac3D`: if true, use `SWFRAC3D` for penetrating shortwave fraction instead of the simpler `SWFRAC` evaluation
- `minKPPhbl`: lower bound on boundary-layer depth

#### Core physical constants and tuning parameters

- `epsln`, `phepsi`, `epsilon`, `vonk`, `dB_dz`
- `conc1`, `conam`, `concm`, `conc2`, `zetam`, `conas`, `concs`, `conc3`, `zetas`
- `Ricr`, `cekman`, `cmonob`, `concv`, `hbf`
- `zmin`, `zmax`, `umin`, `umax`
- `num_v_smooth_Ri`
- `Riinfty`, `BVSQcon`, `difm0`, `difs0`, `dift0`, `difmcon`, `difscon`, `diftcon`
- `Rrho0`, `dsfmax`
- `cstar`

Several older parameters are explicitly rejected as retired by `KPP_READPARMS`.

## 4. File-by-File Functional Map

### Core package state and parameters

- `KPP.h`: declares the package outputs and common blocks for time-varying KPP fields.
- `KPP_PARAMS.h`: declares runtime parameters, lookup tables, vertical-grid helpers, and initialization-time common blocks.
- `KPP_OPTIONS.h`: compile-time switches.

### Initialization and parameter ingestion

- `kpp_readparms.F`: reads `data.kpp` and sets defaults.
- `kpp_init_fixed.F`: computes lookup-table constants, builds turbulent velocity-scale tables, and stores the vertical grid used by KPP.
- `kpp_init_varia.F`: initializes `nzmax` and zeros package arrays.
- `kpp_check.F`: package consistency checks.

### Main runtime computation

- `kpp_calc.F`: main package interface called from the ocean physics driver.
- `kpp_forcing_surf.F`: computes surface-driven KPP forcing terms.
- `kpp_routines.F`: contains the 1-D column physics routines used by `kpp_calc.F`.

### Coupling to MITgcm viscosity and diffusivity operators

- `kpp_calc_visc.F`: inserts KPP viscosity into the model's momentum viscosity fields.
- `kpp_calc_diff_t.F`: returns KPP temperature diffusivity.
- `kpp_calc_diff_s.F`: returns KPP salinity diffusivity.
- `kpp_calc_diff_ptr.F`: returns KPP diffusivity for passive tracers.

### Nonlocal transport terms

- `kpp_transport_t.F`: nonlocal heat flux term.
- `kpp_transport_s.F`: nonlocal salinity flux term.
- `kpp_transport_ptr.F`: nonlocal passive-tracer flux term.

### Diagnostics, output, exchange

- `kpp_diagnostics_init.F`: registers diagnostics fields.
- `kpp_output.F`: writes snapshots and fills diagnostics.
- `kpp_do_exch.F`: exchanges overlap regions for `KPPviscAz`.

### Documentation within package directory

- `kpp_description.tex`: package-specific descriptive text.

## 5. Where KPP Sits in the MITgcm Control Flow

The main call path is:

1. `model/src/do_oceanic_phys.F` decides whether KPP should be computed through `calcKPP`.
2. If active, `do_oceanic_phys.F` calls `KPP_CALC(bi,bj,myTime,myIter,myThid)` for each tile.
3. After tile loops, `do_oceanic_phys.F` calls `KPP_DO_EXCH(myThid)` to exchange overlap values for `KPPviscAz`.
4. Later, the model uses KPP outputs in `calc_viscosity.F` and `calc_3d_diffusivity.F`.
5. At I/O time, `model/src/do_the_model_io.F` calls `KPP_OUTPUT(myTime,myIter,myThid)` if `useKPP` is true.

This division is important: `KPP_CALC` computes and stores package state, but actual momentum and tracer mixing operators consume that state later through separate interfaces.

## 6. Initialization Phase in Detail

### 6.1 `KPP_READPARMS`

`KPP_READPARMS(myThid)` opens `data.kpp`, sets defaults, reads namelist `KPP_PARM01`, then validates parameter usage.

Important input:

- global MITgcm defaults such as `deltaTClock` and `dumpFreq`
- namelist file `data.kpp`

Important output side effects:

- writes values into common blocks declared in `KPP_PARAMS.h`
- sets behavior flags and physical constants used everywhere else in the package

This is the package's primary configuration input path.

### 6.2 `KPP_INIT_FIXED`

`KPP_INIT_FIXED(myThid)` computes constants derived from input parameters and fills lookup tables used for turbulent velocity scales.

Key outputs:

- `Vtc`, `cg`
- lookup tables `wmt` and `wst`
- KPP vertical-grid arrays `zgrid` and `hwide`
- default `minKPPhbl` if user did not set it explicitly

The vertical grid is pulled from MITgcm's existing vertical coordinate arrays, specifically `rC(k)` and `drF(k)`.

### 6.3 `KPP_INIT_VARIA`

`KPP_INIT_VARIA(myThid)` initializes time-varying package state.

Important outputs:

- `nzmax(i,j,bi,bj) = kLowC(i,j,bi,bj)`
- zeroed `KPPhbl`, `KPPghat`, `KPPdiffKzS`, `KPPdiffKzT`
- `KPPviscAz` initialized to `viscArNr(1)`

`nzmax` is the column wet-depth index used later by the KPP column routines.

## 7. Main Runtime Entry Point: `KPP_CALC`

`KPP_CALC` is the package's main interface and the best single routine to understand the package.

### 7.1 Direct routine inputs

Its explicit arguments are only tile and time metadata:

- `bi`, `bj`: tile indices
- `myTime`: current simulation time
- `myIter`: current iteration
- `myThid`: thread id

### 7.2 Effective physical inputs

Most physical inputs arrive through included common blocks and module headers. The main effective inputs are:

#### Ocean state

- `theta`
- `salt`
- `uVel`
- `vVel`

#### Surface forcing

- `surfaceForcingU`
- `surfaceForcingV`
- `surfaceForcingT`
- `surfaceForcingS`
- `adjustColdSST_diag`
- `Qsw`

#### Grid and masks

- `maskC`, `_maskW`, `_maskS`
- `rC`, `rF`, `drF`
- `kLowC`
- `fCori`

#### Existing diffusivity infrastructure

- `CALC_3D_DIFFUSIVITY` is called to supply background tracer diffusivities for salinity and temperature before the KPP column solve.

#### Optional package interactions

- `SaltPlumeDepth`, `saltPlumeFlux`, `SPforcingS`, `SPforcingT` when `ALLOW_SALT_PLUME`
- `SWFRAC3D` when `SHORTWAVE_HEATING` and `KPPuseSWfrac3D`
- `kTopC`, shelf-ice forcing interaction points when `ALLOW_SHELFICE`

### 7.3 Scheduling behavior

KPP does not necessarily recompute every model step. `KPP_CALC` first checks whether `myTime` is a new multiple of `kpp_freq` relative to `deltaTClock`, or whether the run is at `startTime`. If not, previous KPP fields remain in place.

### 7.4 Internal sequence inside `KPP_CALC`

The runtime sequence is:

1. `STATEKPP` computes density-related inputs from `theta` and `salt`.
2. Optional horizontal smoothing is applied to `dbloc`, density-related fields, or both, depending on CPP options.
3. `Ritop` is converted into the bulk-Richardson numerator form used later by `BLDEPTH`.
4. `KPP_FORCING_SURF` computes surface-driven forcing variables such as `ustar`, `bo`, `bosol`, and `dVsq`.
5. `shsq` is computed from vertical velocity shear on the C grid by averaging neighboring U/V-grid differences onto tracer points.
6. Background tracer diffusivities are computed using `CALC_3D_DIFFUSIVITY` for salinity and temperature.
7. If enabled, `KPP_DOUBLEDIFF` modifies those background diffusivities for salt fingering and diffusive convection.
8. `KPPMIX` performs the actual 1-D KPP column solve and returns viscosity, diffusivity, `ghat`, and `hbl`.
9. The local results are transferred into the shared package arrays `KPPviscAz`, `KPPdiffKzS`, `KPPdiffKzT`, `KPPghat`, and `KPPhbl` with masking.
10. If shortwave penetration is enabled, `KPPfrac` is computed from `KPPhbl` and either `SWFRAC3D` or `SWFRAC`.
11. If salt plume support is enabled, `KPPplumefrac` is computed.

### 7.5 Main outputs from `KPP_CALC`

`KPP_CALC` writes into the package state arrays in `KPP.h`:

- `KPPviscAz`
- `KPPdiffKzS`
- `KPPdiffKzT`
- `KPPghat`
- `KPPhbl`
- `KPPfrac`
- `KPPplumefrac` when salt plume support is active

These are its real outputs. The subroutine does not directly update tracer or momentum tendencies.

## 8. Surface-Forcing Routine: `KPP_FORCING_SURF`

`KPP_FORCING_SURF` computes the surface quantities used by the 1-D KPP solver.

### 8.1 Inputs

Direct routine inputs include:

- `rhoSurf`: density of the surface layer
- `surfForcU`, `surfForcV`: momentum forcing components
- `surfForcT`, `surfForcS`: temperature and salinity surface forcing terms
- `surfForcTice`: effective heat flux caused by sea-ice thermodynamics
- `Qsw`: shortwave flux
- `TTALPHA`, `SSBETA`: expansion/contraction coefficients from `STATEKPP`
- `dbloc`: when `KPP_ESTIMATE_UREF` is enabled
- salt-plume forcing arrays when `ALLOW_SALT_PLUME` is enabled

### 8.2 Outputs

- `ustar(i,j)`: friction velocity
- `bo(i,j)`: turbulent surface buoyancy forcing
- `bosol(i,j)`: radiative buoyancy forcing
- `boplume(i,j,k)`: plume-related buoyancy forcing, optional
- `dVsq(i,j,k)`: shear relative to a surface reference velocity

### 8.3 Important formulas and conventions

The code comments make the intended physical meaning explicit:

- `ustar` is computed from the magnitude of surface stress forcing.
- `bo` combines thermal and haline surface buoyancy forcing using `TTALPHA` and `SSBETA`.
- `bosol` uses shortwave radiation and the thermal expansion coefficient.
- `dVsq` is a vertical profile of squared velocity difference relative to a near-surface reference velocity.

This routine is a major input translator: it converts MITgcm forcing fields into KPP's working variables in MKS units.

## 9. The 1-D Column Solver: `KPPMIX`

`KPPMIX` in `kpp_routines.F` is the core KPP column driver.

### 9.1 Inputs

Key direct inputs are:

- `kmtj`: number of vertical wet levels per column
- `shsq`: local vertical shear squared
- `dvsq`: shear relative to the surface reference state
- `ustar`
- `msk`: surface mask
- `bo`, `bosol`
- `boplume`, `SPDepth` when salt plume support is compiled in
- `dbloc`: local buoyancy jump across interfaces
- `Ritop`: bulk-Richardson numerator
- `coriol`
- `swatt` when shortwave penetration is enabled
- `diffusKzS`, `diffusKzT`: background diffusivities for scalar and heat fields

### 9.2 Outputs

- `diffus(:,:,1)`: viscosity profile
- `diffus(:,:,2)`: scalar diffusivity profile
- `diffus(:,:,3)`: temperature diffusivity profile
- `ghat`: nonlocal transport coefficient profile
- `hbl`: mixed-layer depth
- `kbl`: first model level below `hbl` when shortwave support is active

### 9.3 Internal algorithm sequence

`KPPMIX` runs four main stages:

1. `Ri_iwmix`: compute interior mixing coefficients everywhere.
2. `bldepth`: diagnose boundary-layer depth from a bulk Richardson number criterion and determine forcing regime.
3. `blmix`: compute KPP boundary-layer mixing profiles and `ghat`.
4. `enhance`: match/interpolate between interior and boundary-layer coefficients at the boundary-layer base.

Finally, for levels above `kbl`, the boundary-layer coefficients replace or exceed the interior values. Below `kbl`, `ghat` is set to zero.

## 10. Interior Mixing: `Ri_iwmix`

`Ri_iwmix` computes the background and instability-driven interior mixing coefficients. The package comments describe three ingredients:

1. Constant internal-wave background activity.
2. Static instability enhancement when the local stratification is unstable.
3. Shear-instability enhancement as a function of the local Richardson number, unless excluded at compile time.

Its practical outputs feed the `diffus` array returned by `KPPMIX`.

This is the source of vertical mixing below the KPP boundary layer and also the background state onto which boundary-layer mixing is matched.

## 11. Boundary-Layer Depth Diagnosis: `BLDEPTH`

`BLDEPTH` is the routine that determines how deep the KPP boundary layer extends.

### 11.1 Inputs

- `dvsq`
- `dbloc`
- `Ritop`
- `ustar`
- `bo`
- `bosol`
- `boplume`, optional
- `coriol`
- `swatt`, optional

### 11.2 Outputs

- `hbl`: boundary-layer depth
- `bfsfc`: effective surface buoyancy forcing used in the boundary-layer calculation
- `stable`: flag distinguishing stable from unstable forcing
- `casea`: flag identifying the grid-relative location of `hbl`
- `kbl`: index of the first level below `hbl`
- `Rib`: bulk Richardson number profile
- `sigma`: normalized depth coordinate `d / hbl`

### 11.3 Interpretation

The code comments are explicit: the boundary-layer depth is the shallowest depth where the bulk Richardson number reaches the critical value `Ricr`. The routine also determines whether the water column is under stable or unstable surface forcing and packages that decision for later routines.

`BLDEPTH` is therefore the bridge between diagnosed column stability and the enhanced KPP boundary-layer mixing profile.

## 12. Boundary-Layer Mixing: `BLMIX` and `ENHANCE`

`BLMIX` computes the actual KPP polynomial boundary-layer profiles, using:

- `ustar`
- effective surface buoyancy forcing
- `hbl`
- the stability and case flags
- interior diffusivities at the boundary-layer base

Its outputs include:

- `dkm1`: coefficients at the level just above the boundary-layer base
- `blmc`: boundary-layer mixing coefficients
- `ghat`: nonlocal transport coefficient
- `sigma`

`ENHANCE` then adjusts the interface between the interior-mixing profile and the boundary-layer profile so the transition is smooth enough for the scheme's matching conditions.

Practically, these routines produce the elevated mixing coefficients that users usually associate with KPP in the mixed layer.

## 13. State Conversion from Temperature and Salinity: `STATEKPP`

`STATEKPP` is the main translator from model tracer state to KPP buoyancy variables.

### Inputs

- model temperature field `theta`
- model salinity field `salt`
- equation-of-state machinery indirectly included through MITgcm infrastructure

### Outputs

- `sdens`: density of the surface layer
- `dbloc`: local buoyancy jump across interfaces
- `Ritop`: buoyancy difference with respect to the surface, before later scaling in `KPP_CALC`
- `TTALPHA`: thermal expansion coefficient without the `1/rho` factor
- `SSBETA`: haline contraction coefficient without the `1/rho` factor

This routine is critical because all KPP stability and buoyancy forcing calculations depend on these derived fields.

## 14. Double-Diffusion Support: `KPP_DOUBLEDIFF`

`KPP_DOUBLEDIFF` is not the main mixing solver. It is a modifier applied in `KPP_CALC` before `KPPMIX` runs.

### Inputs

- `TTALPHA`, `SSBETA`
- temperature and salinity fields through the included model state
- current background `KPPdiffKzT` and `KPPdiffKzS`

### Outputs

- updated `KPPdiffKzT`
- updated `KPPdiffKzS`

Its role is to add double-diffusive enhancement, such as salt fingering or diffusive convection, before the boundary-layer matching step uses those background profiles.

## 15. How KPP Outputs Enter the Momentum and Tracer Solvers

### 15.1 Viscosity handoff: `KPP_CALC_VISC`

`KPP_CALC_VISC` is called from `model/src/calc_viscosity.F`.

Input:

- level `k`
- existing viscosity arrays `KappaRU` and `KappaRV`
- `KPPviscAz` from the package state

Output:

- updated `KappaRU` and `KappaRV`

Important detail: KPP computes viscosity on tracer points, but momentum viscosity is required on staggered U and V points. The routine averages neighboring tracer-point `KPPviscAz` values onto `_maskW` and `_maskS` locations and inserts them into `KappaRU` and `KappaRV`.

### 15.2 Temperature diffusivity handoff: `KPP_CALC_DIFF_T`

`KPP_CALC_DIFF_T` is called from `model/src/calc_3d_diffusivity.F` when the tracer identity is temperature.

Input:

- tile/range metadata
- `kArg` to request all levels or a single level
- package array `KPPdiffKzT`

Output:

- `KappaRT`

The routine simply copies `KPPdiffKzT` into the model's active temperature diffusivity array.

### 15.3 Salinity diffusivity handoff: `KPP_CALC_DIFF_S`

This is the salinity analogue of `KPP_CALC_DIFF_T`.

Input:

- tile/range metadata
- `kArg`
- package array `KPPdiffKzS`

Output:

- `KappaRS`

### 15.4 Passive tracer diffusivity handoff

`KPP_CALC_DIFF_Ptr` is called for passive tracers. The package comments and transport code make clear that passive tracers do not get a dedicated tracer-specific KPP diffusivity. They use the salinity KPP diffusivity as their vertical mixing coefficient.

## 16. Nonlocal Transport Routines and Their Inputs/Outputs

These routines matter because KPP's nonlocal term is not encoded in `KPPdiffKzT` or `KPPdiffKzS` alone. It is supplied as an additional flux contribution.

### 16.1 `KPP_TRANSPORT_T`

Purpose: add the KPP nonlocal heat transport term to the diffusive heat flux.

Inputs:

- `KPPdiffKzT`
- `KPPghat`
- `surfaceForcingT`
- `adjustColdSST_diag`
- `Qsw`
- `KPPfrac`
- optionally `Kwz` from GM/Redi when `KPP_ghatUseTotalDiffus` is enabled

Output:

- `df(i,j)`: nonlocal contribution to the diffusive heat flux work array

Code-level meaning:

The routine multiplies area, diffusivity, `KPPghat`, and an effective heat-flux forcing term that includes shortwave partitioning.

### 16.2 `KPP_TRANSPORT_S`

Purpose: add the KPP nonlocal salinity transport term.

Inputs:

- `KPPdiffKzS`
- `KPPghat`
- `surfaceForcingS`
- optional salt-plume surface contribution
- optional total diffusivity augmentation through GM/Redi

Output:

- `df(i,j)`: nonlocal contribution to salinity diffusive flux

### 16.3 `KPP_TRANSPORT_PTR`

Purpose: add the KPP nonlocal passive-tracer transport term.

Inputs:

- `KPPdiffKzS` or, in offline mode, preloaded `KPPghat` containing `ghat * diffKzS`
- `KPPghat`
- `surfaceForcingPTr(:,:,:,iTr)`

Output:

- `df(i,j)`: nonlocal passive-tracer flux contribution

Important design detail: passive tracers reuse salinity diffusivity.

## 17. Diagnostics and Snapshot Output

### 17.1 Registered diagnostics

`KPP_DIAGNOSTICS_INIT` registers diagnostics including:

- `KPPviscA`
- `KPPdiffS`
- `KPPdiffT`
- `KPPghatK`
- `KPPhbl`
- `KPPfrac`
- `KPPdbsfc`
- `KPPbfsfc`
- `KPPRi`
- `KPPbo`
- `KPPbosol`
- `KPPdbloc`
- `KPPshsq`
- `KPPdVsq`
- `KPPnuddt`, `KPPnudds` when double diffusion is present
- `KPPg...` fields for nonlocal scalar fluxes
- `KPPpfrac` and `KPPboplm` when salt plume support is present

### 17.2 Snapshot writer: `KPP_OUTPUT`

`KPP_OUTPUT` runs from `do_the_model_io.F`.

Inputs:

- `myTime`, `myIter`, `myThid`
- `kpp_dumpFreq`
- `KPPwriteState`
- package state arrays

Outputs:

- MDSIO snapshot files or MNC records for `KPPviscAz`, `KPPdiffKzT`, `KPPdiffKzS`, `KPPghat`, `KPPhbl`
- diagnostics-package fills for the registered KPP fields

The output routine does not recompute physics. It only serializes and publishes existing KPP state.

## 18. Parallel Exchange

`KPP_DO_EXCH(myThid)` exchanges overlap regions for `KPPviscAz`.

This is a narrower exchange than some users might expect. The routine only exchanges the viscosity array directly. Other KPP fields are either used locally in the way the model is structured or are handled through other mechanisms.

## 19. Input/Output Summary by Category

### 19.1 User-provided inputs

- compile-time package enablement and CPP flags
- `data.pkg` with `useKPP = .TRUE.`
- `data.kpp` namelist values

### 19.2 Model-state inputs consumed by KPP

- `theta`, `salt`
- `uVel`, `vVel`
- density and EOS support through MITgcm infrastructure

### 19.3 Surface-forcing inputs consumed by KPP

- `surfaceForcingU`, `surfaceForcingV`
- `surfaceForcingT`, `surfaceForcingS`
- `adjustColdSST_diag`
- `Qsw`
- optional sea-ice, shelf-ice, and salt-plume forcings

### 19.4 Grid and geometry inputs consumed by KPP

- `rC`, `rF`, `drF`
- masks and wet-level indices
- `fCori`

### 19.5 Main computational outputs

- `KPPviscAz`
- `KPPdiffKzT`
- `KPPdiffKzS`
- `KPPghat`
- `KPPhbl`
- `KPPfrac`
- `KPPplumefrac`, optional

### 19.6 Downstream model effects

- modifies vertical momentum viscosity through `KPP_CALC_VISC`
- modifies vertical tracer diffusivity through `KPP_CALC_DIFF_*`
- adds nonlocal flux terms for temperature, salinity, and passive tracers through `KPP_TRANSPORT_*`
- provides diagnostic and snapshot products through `KPP_OUTPUT`

## 20. Temperature, Salinity, Momentum, and Passive Tracer Differences

The package does not treat all prognostic quantities identically.

### Momentum

- uses `KPPviscAz`
- no nonlocal `ghat` transport term
- tracer-point viscosity is averaged onto velocity points before use

### Temperature

- uses `KPPdiffKzT`
- has a nonlocal transport term via `KPP_TRANSPORT_T`
- shortwave radiation enters both the boundary-layer diagnosis and the nonlocal temperature flux through `KPPfrac`

### Salinity

- uses `KPPdiffKzS`
- has a nonlocal transport term via `KPP_TRANSPORT_S`
- can be modified by salt-plume and double-diffusive effects

### Passive tracers

- use the salinity diffusivity path, not a unique tracer-specific KPP diffusivity
- have a nonlocal flux path through `KPP_TRANSPORT_PTR`

This distinction is one of the most important package outputs from an interface point of view.

## 21. Practical Interpretation of the Package Interface

For users or developers interfacing with KPP, the most important fact is this:

KPP's real API to the rest of MITgcm is not a single function call with explicit arguments and return values. Its effective interface is the package state in `KPP.h` plus the downstream routines that consume that state.

If you need to know what KPP is supplying to the model, inspect:

- `KPPviscAz`
- `KPPdiffKzT`
- `KPPdiffKzS`
- `KPPghat`
- `KPPhbl`
- `KPPfrac`

If you need to know what KPP depends on, inspect:

- `theta`, `salt`, `uVel`, `vVel`
- the surface forcing arrays
- the grid and mask arrays
- `data.kpp` parameters and relevant CPP options

## 22. Key Conclusions

1. `KPP_CALC` is the operational center of the package, but the actual physical profile solve is delegated to `KPPMIX` and its helper routines.
2. The package's main outputs are shared vertical viscosity, diffusivity, nonlocal transport, and mixed-layer-depth fields, not direct tracer tendencies.
3. Temperature, salinity, and passive tracers share much of the same machinery, but temperature has dedicated diffusivity and shortwave handling, while passive tracers reuse salinity diffusivity.
4. The nonlocal transport path is separate from the diffusivity path and must be considered if one wants the full KPP effect on scalar budgets.
5. The most important user-controlled inputs are the `data.kpp` namelist, the compile-time CPP options, and the external MITgcm forcing and state fields that `KPP_CALC` reads through included common blocks.

## 23. Source Files Examined

Primary files examined for this report:

- `doc/phys_pkgs/kpp.rst`
- `pkg/kpp/KPP.h`
- `pkg/kpp/KPP_PARAMS.h`
- `pkg/kpp/KPP_OPTIONS.h`
- `pkg/kpp/kpp_readparms.F`
- `pkg/kpp/kpp_init_fixed.F`
- `pkg/kpp/kpp_init_varia.F`
- `pkg/kpp/kpp_calc.F`
- `pkg/kpp/kpp_forcing_surf.F`
- `pkg/kpp/kpp_routines.F`
- `pkg/kpp/kpp_calc_visc.F`
- `pkg/kpp/kpp_calc_diff_t.F`
- `pkg/kpp/kpp_calc_diff_s.F`
- `pkg/kpp/kpp_transport_t.F`
- `pkg/kpp/kpp_transport_s.F`
- `pkg/kpp/kpp_transport_ptr.F`
- `pkg/kpp/kpp_diagnostics_init.F`
- `pkg/kpp/kpp_output.F`
- `pkg/kpp/kpp_do_exch.F`
- selected call sites in `model/src/do_oceanic_phys.F`, `model/src/calc_3d_diffusivity.F`, `model/src/calc_viscosity.F`, and `model/src/do_the_model_io.F`