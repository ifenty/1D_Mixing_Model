"""
GGL90 Parameters Module

This module defines the parameters for the GGL90 turbulent kinetic energy
(TKE) mixing scheme as implemented in MITgcm.

Reference:
    Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990), JGR, 95(C9), pp. 16,179
"""

import numpy as np
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# Default parameter YAML shipped alongside this module (like MITgcm's built-in
# defaults). from_yaml() always loads this first, then overlays any user file.
_DEFAULT_PARAMS_YAML = Path(__file__).resolve().parent / "ggl90_default_parameters.yaml"


@dataclass
class GGL90Parameters:
    """
    Parameters for GGL90 vertical mixing scheme.

    Attributes:
        Physical Parameters:
        -------------------
        ck : float
            Viscosity coefficient (eq.10 in Gaspar et al. 1990)
            Default: 0.1
        ceps : float
            Dissipation coefficient (Kolmogorov 1942)
            Default: 0.7
        alpha : float
            TKE diffusivity multiplier (KappaE/KappaM).
            MITgcm computes tracer diffusivity from the turbulent Prandtl
            number, not directly from alpha.
            Default: 10.0. The original GGL90 paper (Gaspar et al. 1990)
            uses 1.0, but that produces cell-to-cell TKE oscillations on
            this grid (oscillation-free for alpha >= 5). Set alpha=1.0 to
            reproduce the paper; ECCOv4 R4 uses 30.0.
        m2 : float
            Wind stress to vertical stress ratio for TKE boundary condition
            Default: 3.75 (Blanke and Delecluse 1993)

        TKE Limits:
        -----------
        tke_min : float
            Minimum TKE for regularization and background processes (m²/s²)
            Default: 1.0e-11 (ECCOv4 R4 uses 1.0e-7)
        tke_surf_min : float
            Minimum surface TKE (m²/s²)
            Default: 1.0e-4
        tke_bottom : float
            Bottom boundary TKE (m²/s²)
            Default: tke_min (ECCOv4 R4 uses 1.0e-6)

        Mixing Length:
        -------------
        mixing_length_min : float
            Minimum mixing length (m)
            Default: 1.0e-8
        mxl_max_flag : int
            Mixing length limiting method (0, 1, or 2)
            0: Simple depth limit
            1: Distance to surface or bottom
            2: Two-way sweep (Blanke & Delecluse 1993) [ECCOv4 R4]
            Default: 0
        mxl_surf_flag : bool
            Force mixing between first and second level
            Default: False (ECCOv4 R4 uses True)

        Viscosity/Diffusivity Limits:
        -----------------------------
        visc_max : float
            Maximum viscosity (m²/s)
            Default: 100.0
        diff_max : float
            Maximum diffusivity (m²/s)
            Default: 100.0
        diff_tke_h : float
            Horizontal TKE diffusivity (m²/s)
            Default: 0.0

        Boundary Conditions:
        -------------------
        use_dirichlet : bool
            Use Dirichlet boundary conditions for TKE
            True: TKE(bottom) = tke_bottom
            False: dTKE/dz(bottom) = 0
            Default: True
        calc_mean_vert_shear : bool
            Calculate mean vertical shear at grid center (vs shear of mean flow)
            Default: False

        Optional Features:
        -----------------
        use_idemix : bool
            Enable IDEMIX internal wave model
            Default: False
        use_langmuir : bool
            Enable Langmuir circulation parameterization
            Default: False
        use_smooth : bool
            Enable horizontal smoothing (ALLOW_GGL90_SMOOTH)
            Default: False

        Numerical:
        ---------
        impl_diss_fac : float
            Implicit dissipation factor (0 to 1)
            Default: 1.0 (fully implicit)
        expl_diss_fac : float
            Explicit dissipation factor (0 to 1)
            Default: 0.0
    """

    # Physical parameters
    ck: float = 0.1
    ceps: float = 0.7
    # TKE diffusivity multiplier (KappaE/KappaM). Original GGL90 paper
    # (Gaspar et al. 1990) uses 1.0; we default to 10.0 because 1.0 produces
    # cell-to-cell TKE oscillations on this grid (oscillation-free for
    # alpha >= 5). Set alpha=1.0 to reproduce the paper; ECCOv4 R4 uses 30.0.
    alpha: float = 10.0
    m2: float = 3.75

    # TKE limits
    tke_min: float = 1.0e-11
    tke_surf_min: float = 1.0e-4
    tke_bottom: Optional[float] = None

    # Mixing length
    mixing_length_min: float = 1.0e-8
    mxl_max_flag: int = 0
    mxl_surf_flag: bool = False

    # Viscosity/diffusivity limits
    visc_max: float = 100.0
    diff_max: float = 100.0
    diff_tke_h: float = 0.0

    # Boundary conditions
    use_dirichlet: bool = True
    calc_mean_vert_shear: bool = False

    # Optional features
    use_idemix: bool = False
    use_langmuir: bool = False
    use_smooth: bool = False

    # Numerical
    impl_diss_fac: float = 1.0
    expl_diss_fac: float = 0.0

    # Constants
    sqrt_two: float = np.sqrt(2.0)
    ggl90_eps: float = 2.23e-16

    def __post_init__(self):
        """Initialize derived parameters and validate settings."""
        # Set default tke_bottom if not specified
        if self.tke_bottom is None:
            self.tke_bottom = self.tke_min

        # Validate parameters
        self._validate()

    def _validate(self):
        """Validate parameter values."""
        if self.tke_min <= 0:
            raise ValueError("tke_min must be greater than zero")
        if self.tke_bottom < 0:
            raise ValueError("tke_bottom must not be less than zero")
        if self.mixing_length_min <= 0:
            raise ValueError("mixing_length_min must be greater than zero")
        if self.visc_max <= 0:
            raise ValueError("visc_max must be greater than zero")
        if self.diff_max <= 0:
            raise ValueError("diff_max must be greater than zero")
        if self.mxl_max_flag not in [0, 1, 2, 3]:
            raise ValueError("mxl_max_flag must be 0, 1, 2, or 3")
        if self.impl_diss_fac < 0 or self.impl_diss_fac > 1:
            raise ValueError("impl_diss_fac must be between 0 and 1")
        if self.expl_diss_fac < 0 or self.expl_diss_fac > 1:
            raise ValueError("expl_diss_fac must be between 0 and 1")

    @classmethod
    def from_yaml(cls, user_yaml_path: Optional[Union[str, Path]] = None
                  ) -> "GGL90Parameters":
        """Load GGL90 parameters: defaults first, then optional user overrides.

        This mirrors MITgcm's data.ggl90 workflow: the built-in default
        parameters (ggl90_default_parameters.yaml, shipped next to this module)
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
        GGL90Parameters
        """
        with open(_DEFAULT_PARAMS_YAML, "r") as f:
            merged = yaml.safe_load(f) or {}
        if not isinstance(merged, dict):
            raise ValueError(
                f"{_DEFAULT_PARAMS_YAML}: default GGL90 YAML must be a mapping"
            )

        if user_yaml_path is not None:
            with open(user_yaml_path, "r") as f:
                user = yaml.safe_load(f) or {}
            if not isinstance(user, dict):
                raise ValueError(f"{user_yaml_path}: GGL90 YAML must be a mapping")
            merged.update(user)  # user keys override defaults

        return cls(**merged)

    def to_yaml(self, yaml_path: str) -> None:
        """Save current parameter values to YAML."""
        from dataclasses import asdict

        cfg = asdict(self)
        with open(yaml_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

    def print_summary(self):
        """Print a summary of parameter settings."""
        print("=" * 60)
        print("GGL90 Parameter Configuration")
        print("=" * 60)
        print("\nPhysical Parameters:")
        print(f"  ck (viscosity coeff.)        : {self.ck}")
        print(f"  ceps (dissipation coeff.)    : {self.ceps}")
        print(f"  alpha (TKE transport factor) : {self.alpha}")
        print(f"  m2 (wind stress ratio)       : {self.m2}")

        print("\nTKE Limits:")
        print(f"  tke_min                      : {self.tke_min:.2e} m²/s²")
        print(f"  tke_surf_min                 : {self.tke_surf_min:.2e} m²/s²")
        print(f"  tke_bottom                   : {self.tke_bottom:.2e} m²/s²")

        print("\nMixing Length:")
        print(f"  mixing_length_min            : {self.mixing_length_min:.2e} m")
        print(f"  mxl_max_flag                 : {self.mxl_max_flag}")
        print(f"  mxl_surf_flag                : {self.mxl_surf_flag}")

        print("\nViscosity/Diffusivity Limits:")
        print(f"  visc_max                     : {self.visc_max} m²/s")
        print(f"  diff_max                     : {self.diff_max} m²/s")
        print(f"  diff_tke_h                   : {self.diff_tke_h} m²/s")

        print("\nBoundary Conditions:")
        print(f"  use_dirichlet                : {self.use_dirichlet}")
        print(f"  calc_mean_vert_shear         : {self.calc_mean_vert_shear}")

        print("\nOptional Features:")
        print(f"  use_idemix                   : {self.use_idemix}")
        print(f"  use_langmuir                 : {self.use_langmuir}")
        print(f"  use_smooth                   : {self.use_smooth}")

        print("\nNumerical:")
        print(f"  impl_diss_fac                : {self.impl_diss_fac}")
        print(f"  expl_diss_fac                : {self.expl_diss_fac}")
        print("=" * 60)
