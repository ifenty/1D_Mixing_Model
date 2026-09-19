# MITgcm ↔ Python vertical-staggering map

This Python 1-D column model reproduces MITgcm's vertical grid staggering
**exactly**, so its output arrays overlay F77 MITgcm output **index-for-index**
with no re-indexing or interpolation. This document records the convention and
the array-to-array mapping to use when comparing against MITgcm output.

## Convention (0-based Python index `k`)

- Cell centers hold tracers/velocities: `theta[k]`, `salt[k]`, `u_vel[k]`,
  `v_vel[k]` at the center of cell `k` (MITgcm `rC(k)`).
- **Interface (W-point) arrays** use index `k` = **top face of cell k** = the
  interface between cell `k-1` (above) and cell `k` (below). Index `k=0` is the
  ocean surface face. This is MITgcm's `rF(k)` layout.
- Surface face carries no diffusive flux: `diffKz[0] = viscAz[0] = 0`
  (MITgcm `KPPdiffKzT(1)=0`).
- The vertical diffusive flux through the top face of cell `k` is
  `-K[k] * (C[k] - C[k-1]) / drC[k]`, where `drC[k] = depth[k-1] - depth[k]`
  is the center-to-center distance (MITgcm `gad_diff_r.F`).

## Index offsets, in Python (0-based) vs MITgcm Fortran (1-based)

MITgcm surface interface is Fortran index `k=1`; Python surface interface is
`k=0`. So `PythonArray[k]  <->  MITgcmArray(k+1)` for interface quantities, and
likewise for cell-centered quantities. No half-cell shift, no averaging.

## Array map

| Physical quantity                | Python (this code)        | MITgcm F77 array         | Location (index k) |
|----------------------------------|---------------------------|--------------------------|--------------------|
| Temperature                      | `theta[k]`                | `theta(...,k)`           | center of cell k   |
| Salinity                         | `salt[k]`                 | `salt(...,k)`            | center of cell k   |
| Zonal velocity                   | `u_vel[k]`                | `uVel(...,k)`            | center of cell k   |
| Meridional velocity              | `v_vel[k]`                | `vVel(...,k)`            | center of cell k   |
| **KPP** vertical viscosity       | `KPPOutput.visc_az[k]`    | `KPPviscAz(...,k)`       | top face of cell k; index 0 = 0 |
| **KPP** salt diffusivity         | `KPPOutput.diff_kz_s[k]`  | `KPPdiffKzS(...,k)`      | top face of cell k; index 0 = 0 |
| **KPP** temp diffusivity         | `KPPOutput.diff_kz_t[k]`  | `KPPdiffKzT(...,k)`      | top face of cell k; index 0 = 0 |
| **KPP** nonlocal transport       | `KPPOutput.ghat[k]`       | `KPPghat(...,k)`         | **bottom** face of cell k (half-level offset) |
| **KPP** boundary-layer depth     | `KPPOutput.hbl`           | `KPPhbl`                 | scalar [m]         |
| **GGL90** TKE (prognostic)       | `tke[k]`                  | `GGL90TKE(...,k)`        | top face of cell k |
| **GGL90** vertical viscosity     | `GGL90Output.kappa_m[k]`  | `GGL90viscAz(...,k)`     | top face of cell k; index 0 = 0 |
| **GGL90** diffusivity            | `GGL90Output.kappa_h[k]`  | `GGL90diffKr(...,k)`     | top face of cell k; index 0 = 0 |
| **GGL90** mixing length          | `GGL90Output.mixing_length[k]` | `GGL90mixingLength(...,k)` | top face of cell k |
| **GGL90** N² (buoyancy freq.)    | `GGL90Output.n_square[k]` | `Nsquare(...,k)`         | top face of cell k; index 0 = 0 |

## Notes / gotchas

- **`ghat` is deliberately offset** from `diffKz` by half a level in MITgcm
  (`kpp_transport_t.F:21-25`): `diffKz` at the top of cell k, `ghat` at the
  bottom of cell k. The diffusion flux through the top face of cell k pairs
  `diffKz[k]` with `ghat[k-1]`. This is preserved, not "fixed."
- **KPP internal vs output.** Internally KPP computes on a bottom-of-cell grid
  (like MITgcm's `kpp_routines.F` `diffus(i,k,mr)`), then shifts by +1 on output
  (`kpp_core.py` Step 9, mirroring MITgcm `kpp_calc.F:574-588`
  `vddiff(k-1) -> KPPdiffKzT(k)`). Compare against MITgcm's **output** arrays,
  not its internal `diffus`.
- **EOS is orthogonal.** Staggering is identical for the linear and JMD95 EOS
  (`main/eos.py`); pick the EOS to match the MITgcm run being compared.
- **Verification.** `main/test_staggering.py` encodes these placements as
  assertions. The KPP time-stepped tracer solution is provably unchanged by the
  output relabeling (it is a pure relabel + a symmetric solver update);
  regression against a pre-change baseline shows `max|Δ| = 0`.
