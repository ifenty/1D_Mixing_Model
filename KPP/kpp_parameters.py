"""
KPP parameters class with defaults loaded from YAML.

All CPP #ifdef blocks from Fortran are converted to boolean parameters.
Follows MITgcm convention where users can override defaults with a data.kpp-like file.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict

# Default parameter YAML shipped alongside this module (like MITgcm's built-in
# defaults). from_yaml() always loads this first, then overlays any user file.
_DEFAULT_PARAMS_YAML = Path(__file__).resolve().parent / "kpp_default_parameters.yaml"


@dataclass
class KPPParameters:
    """
    KPP configuration parameters.

    All parameters have defaults matching MITgcm pkg/kpp implementation.
    Can be loaded from YAML file or modified programmatically.
    """

    # ========== CPP Options (from KPP_OPTIONS.h) ==========
    # Horizontal smoothing options
    smooth_shsq: bool = True  # KPP_SMOOTH_SHSQ: smooth shear horizontally
    smooth_dvsq: bool = False  # KPP_SMOOTH_DVSQ: smooth dVsq horizontally
    smooth_dbloc: bool = True  # KPP_SMOOTH_DBLOC: smooth dbloc horizontally
    smooth_dens: bool = False  # KPP_SMOOTH_DENS: smooth all density variables
    smooth_visc: bool = False  # KPP_SMOOTH_VISC: smooth vertical viscosity
    smooth_diff: bool = False  # KPP_SMOOTH_DIFF: smooth vertical diffusivity

    # Velocity reference estimation
    estimate_uref: bool = False  # KPP_ESTIMATE_UREF: resolution-independent surface velocity

    # Matching options
    match_diffusivities: bool = True  # NOT KPP_DO_NOT_MATCH_DIFFUSIVITIES
    match_derivatives: bool = True  # NOT KPP_DO_NOT_MATCH_DERIVATIVES

    # Regularization
    smooth_regularisation: bool = False  # KPP_SMOOTH_REGULARISATION

    # Shear mixing scaling
    scale_shearmixing: bool = False  # KPP_SCALE_SHEARMIXING (Polzin 1996)

    # Nonlocal transport
    use_ghat: bool = True  # KPP_GHAT: include nonlocal transport term

    # Interior mixing options
    exclude_shear_mix: bool = False  # EXCLUDE_KPP_SHEAR_MIX
    exclude_doublediff: bool = False  # EXCLUDE_KPP_DOUBLEDIFF

    # Vertical smoothing
    vertically_smooth_ri: bool = False  # ALLOW_KPP_VERTICALLY_SMOOTH
    num_v_smooth_ri: int = 0  # Number of vertical smoothing passes for Ri

    # ========== Physical Parameters (from KPP_PARAMS.h) ==========
    # Boundary layer depth parameters
    Ricr: float = 0.3  # Critical bulk Richardson number
    cekman: float = 0.7  # Ekman depth coefficient
    cmonob: float = 1.0  # Monin-Obukhov depth coefficient
    concv: float = 1.8  # Ratio of interior to entrainment buoyancy freq
    hbf: float = 1.0  # Fraction of hbl for absorbed solar radiation

    # Universal constants
    epsln: float = 1.0e-20  # Small number
    phepsi: float = 1.0e-10  # Small number for regularization
    epsilon: float = 0.1  # Nondimensional extent of surface layer
    vonk: float = 0.4  # von Karman constant
    dB_dz: float = 5.2e-5  # Maximum dB/dz in mixed layer [s^-2]

    # Shape function coefficients
    conc1: float = 5.0
    conam: float = 1.257
    concm: float = 8.380
    conc2: float = 16.0
    zetam: float = -0.2
    conas: float = -28.86
    concs: float = 98.96
    conc3: float = 16.0
    zetas: float = -1.0

    # Lookup table parameters
    zmin: float = -4.0e-7  # Minimum zehat in lookup table [m^3/s^3]
    zmax: float = 0.0  # Maximum zehat in lookup table
    umin: float = 0.0  # Minimum ustar in lookup table [m/s]
    umax: float = 0.04  # Maximum ustar in lookup table [m/s]

    # Interior mixing parameters
    Riinfty: float = 0.7  # Local Richardson number limit for shear instability
    BVSQcon: float = -0.2e-4  # Brunt-Vaisala squared for convection [1/s^2]
    difm0: float = 5.0e-3  # Viscosity max due to shear instability [m^2/s]
    difs0: float = 5.0e-3  # Tracer diffusivity max due to shear instability [m^2/s]
    dift0: float = 5.0e-3  # Heat diffusivity max due to shear instability [m^2/s]
    difmcon: float = 0.1  # Viscosity due to convective instability [m^2/s]
    difscon: float = 0.1  # Tracer diffusivity due to convective instability [m^2/s]
    diftcon: float = 0.1  # Heat diffusivity due to convective instability [m^2/s]

    # Double diffusion parameters
    Rrho0: float = 1.9  # Density ratio limit for salt fingering
    dsfmax: float = 1.0e-2  # Maximum diffusivity for salt fingering [m^2/s]

    # Boundary layer mixing parameters
    cstar: float = 10.0  # Proportionality coefficient for nonlocal transport

    # Flags
    use_doublediff: bool = False  # KPPuseDoubleDiff
    limit_hbl_stable: bool = True  # LimitHblStable
    ghat_use_total_diffus: bool = False  # KPP_ghatUseTotalDiffus
    kpp_write_state: bool = False  # KPPwriteState (diagnostic output only, no-op here)

    # ========== MITgcm bug-compatibility switch ==========
    # When True, reproduce the *exact* stock-MITgcm pkg/kpp behaviour, including
    # a known numerical hazard that the MITgcm developers themselves flagged in
    # the source but left active. When False (default), branch to bug-fixed code.
    #
    # This flag ONLY gates places where the stock Fortran77 is genuinely wrong
    # (or hazardous) AND the fix diverges from the MITgcm reference solution.
    # Pure Python porting errors (wrong index, inverted sign, missing /dz, etc.)
    # are corrected unconditionally, because for those the Fortran is correct and
    # fixing the port is exactly how we reproduce MITgcm. See VALIDATION_REPORT_V2.md.
    #
    # Currently gated bug(s):
    #   - wscale zdiff linear-extrapolation hazard (kpp_routines.F:980 vs :990)
    keep_mitgcm_bugs: bool = False

    # ========== Shortwave penetration (SHORTWAVE_HEATING / selectPenetratingSW) ==========
    shortwave_heating: bool = False  # Whether Qsw is treated as a separate penetrating flux
    select_penetrating_sw: int = 0  # 0 = off, >=1 = on (mirrors MITgcm selectPenetratingSW)
    jerlov_water_type: str = "IB"  # One of "I", "IA", "IB", "II", "III" (see shortwave.py)
    use_sw_frac_3d: bool = False  # KPPuseSWfrac3D: spatially varying water type (not implemented)

    # ========== Salt plume (ALLOW_SALT_PLUME) ==========
    allow_salt_plume: bool = False  # Compiled-in support (not implemented)
    use_salt_plume: bool = False  # Runtime useSALT_PLUME (not implemented)
    salt_plume_volume: bool = False  # SALT_PLUME_VOLUME variant (not implemented)

    # ========== Shelf ice (ALLOW_SHELFICE) ==========
    allow_shelfice: bool = False  # Ice-shelf boundary layer coupling (not implemented)

    # Minimum boundary layer depth [m]
    min_kpp_hbl: Optional[float] = None  # If None, set to surface grid spacing

    # Physical constants (loaded from configuration_yamls/physical_parameters.yaml by unified driver).
    # These defaults match MITgcm/ECCO standard values.
    gravity: float = 9.81  # Gravitational acceleration [m/s^2]
    rho_const: float = 1029.0  # Reference density [kg/m^3]
    heat_capacity_cp: float = 3994.0  # Heat capacity [J/kg/K]

    # ========== Numerical Constants (for regularization) ==========
    epsln: float = 1.0e-20  # Small number for regularization
    phepsi: float = 1.0e-10  # Small number for regularization

    # ========== Lookup Table Dimensions ==========
    nni: int = 890  # Number of zehat values in lookup table
    nnj: int = 480  # Number of ustar values in lookup table

    # ========== Computational Parameters ==========
    mdiff: int = 3  # Number of diffusivities (visc, salt, temp)

    def __post_init__(self):
        """Validate and compute derived parameters."""
        # Compute Vtc (turbulent velocity scale coefficient)
        import numpy as np
        self.Vtc = self.concv * np.sqrt(0.2 / self.concs / self.epsilon) / self.vonk**2 / self.Ricr

        # Compute cg (counter-gradient coefficient)
        self.cg = self.cstar * self.vonk * (self.concs * self.vonk * self.epsilon)**(1.0/3.0)

        # Consistency checks
        if self.smooth_dens:
            self.smooth_dbloc = True

        if not self.match_diffusivities:
            self.match_derivatives = False

        # These modules are flagged for future work but not yet ported; fail loudly
        # rather than silently producing physics that ignores the requested option.
        unimplemented = []
        if self.allow_salt_plume or self.use_salt_plume:
            unimplemented.append("salt plume (allow_salt_plume/use_salt_plume)")
        if self.allow_shelfice:
            unimplemented.append("shelf ice coupling (allow_shelfice)")
        if self.use_sw_frac_3d:
            unimplemented.append("3D shortwave water-type field (use_sw_frac_3d)")
        if unimplemented:
            raise NotImplementedError(
                "KPPConfig option(s) not yet implemented in this Python port: "
                + "; ".join(unimplemented)
            )

    @classmethod
    def from_yaml(cls, user_yaml_path: Optional[Union[str, Path]] = None
                  ) -> 'KPPParameters':
        """Load KPP parameters: defaults first, then optional user overrides.

        This mirrors MITgcm's data.kpp workflow: the built-in default
        parameters (kpp_default_parameters.yaml, shipped next to this module)
        are always loaded first, and if the user supplies their own YAML, only
        the keys present in that file override the defaults. Any keys the user
        omits keep their default value.

        Parameters
        ----------
        user_yaml_path : str or Path, optional
            Path to a user parameter YAML with a subset of keys to override.
            If None, the returned parameters are exactly the defaults.

        Returns
        -------
        KPPParameters
        """
        with open(_DEFAULT_PARAMS_YAML, 'r') as f:
            merged = yaml.safe_load(f) or {}
        if not isinstance(merged, dict):
            raise ValueError(
                f"{_DEFAULT_PARAMS_YAML}: default KPP YAML must be a mapping"
            )

        if user_yaml_path is not None:
            with open(user_yaml_path, 'r') as f:
                user = yaml.safe_load(f) or {}
            if not isinstance(user, dict):
                raise ValueError(f"{user_yaml_path}: KPP YAML must be a mapping")
            merged.update(user)  # user keys override defaults

        return cls(**merged)

    def to_yaml(self, yaml_path: str):
        """
        Save configuration to YAML file.

        Parameters
        ----------
        yaml_path : str
            Path to output YAML file
        """
        config_dict = asdict(self)
        # Remove computed parameters
        config_dict.pop('Vtc', None)
        config_dict.pop('cg', None)

        with open(yaml_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    def __repr__(self) -> str:
        """String representation showing key parameters."""
        return (
            f"KPPConfig(\n"
            f"  Ricr={self.Ricr}, Riinfty={self.Riinfty}\n"
            f"  difm0={self.difm0}, difmcon={self.difmcon}\n"
            f"  use_ghat={self.use_ghat}, use_doublediff={self.use_doublediff}\n"
            f"  smooth_shsq={self.smooth_shsq}, smooth_dbloc={self.smooth_dbloc}\n"
            f")"
        )
