# KPP Validation Data Summary

## Output File Location
`/tmp/mitgcm_run_output_fixed.txt` (27MB)

## Data Structure

### Timesteps Captured
9 timesteps (myIter = 1 through 9)

### Grid Configuration
- Single tile: BI=1, BJ=1
- Grid size: Multiple i,j points (need to check SIZE.h for exact dimensions)
- Vertical levels: Nr levels (appears to be 23 based on output)

### Data Fields Per Timestep

#### INPUT_STATE (cell centers, k=1..Nr)
Format: `INPUT_STATE,i,j,k,theta,salt,uvel,vvel,depth_center`
- theta: Potential temperature (deg C)
- salt: Salinity (psu)
- uvel: U-velocity (m/s)
- vvel: V-velocity (m/s)
- depth_center: Depth at cell center (m, negative)

#### INPUT_GEOM (cell geometry, k=1..Nr)
Format: `INPUT_GEOM,i,j,k,drF,rF,rC`
- drF: Cell thickness (m)
- rF: Interface depth (m)
- rC: Cell center depth (m)

#### INPUT_FORCING (surface forcing, per column)
Format: `INPUT_FORCING,i,j,tau_x,tau_y,q_net,q_sw,fw_flux`
- tau_x: Surface wind stress in x (N/m^2)
- tau_y: Surface wind stress in y (N/m^2)
- q_net: Net heat flux (W/m^2)
- q_sw: Shortwave radiation (W/m^2)
- fw_flux: Freshwater flux (m/s)

#### INPUT_CORIOLIS (per column)
Format: `INPUT_CORIOLIS,i,j,f_coriolis`
- f_coriolis: Coriolis parameter (1/s)

#### OUTPUT_MIXING (mixing coefficients at interfaces, k=1..Nr)
Format: `OUTPUT_MIXING,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat,depth_interface`
- visc_az: Vertical viscosity (m^2/s)
- diff_kz_s: Salt diffusivity (m^2/s)
- diff_kz_t: Temperature diffusivity (m^2/s)
- ghat: Non-local transport term (m/s)
- depth_interface: Depth at interface (m)

#### OUTPUT_HBL (boundary layer depth, per column)
Format: `OUTPUT_HBL,i,j,hbl`
- hbl: Boundary layer depth (m)

## Data Quality

### Precision
- All floating point values in E25.16 format (16 significant digits)
- Suitable for rtol=1e-12 validation testing

### Non-Zero Data Observed
- Surface forcing (shortwave radiation): -72.7 W/m^2
- Depths properly negative
- Most state variables zero at early timesteps (cold start)

### Data Markers
Each timestep block delimited by:
- Start: `===== KPP_VALIDATION_START =====`
- Header: `TIMESTEP=N,BI=bi,BJ=bj`
- End: `===== KPP_VALIDATION_END =====`

Debug line also present:
`DEBUG: KPP_OUTPUT_VALIDATION, myIter=N myThid=1`

## Next Steps

1. Parse this file to extract validation data
2. Create structured test cases for Python KPP implementation
3. Run Python port and compare outputs with rtol=1e-12, atol=1e-14
