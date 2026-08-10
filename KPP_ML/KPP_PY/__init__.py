"""
Python implementation of MITgcm KPP mixing scheme.

This package provides a Python translation of the MITgcm KPP (K-Profile Parameterization)
vertical mixing scheme for generating machine learning training data.

Main modules (refactored for code clarity and reuse):
    - kpp_parameters: Parameter configuration
    - kpp_scheme_specific: KPP-specific logic (boundary layer diagnostics, mixing)
    - kpp_routines: Core mixing routines (Richardson number interior mixing, velocity scales)
    - kpp_core_driver: Core KPP driver orchestration
    - kpp_shortwave: Shortwave radiation penetration (specialized, no duplication)

Based on:
- Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing:
  A review and a model with a nonlocal boundary layer parameterization.
  Reviews of Geophysics, 32(4), 363-403.
- MITgcm pkg/kpp implementation
"""

from .kpp_parameters import KPPParameters
from .kpp_core_driver import KPPDriver, KPPOutput

__version__ = "2.0.0"
__all__ = ["KPPParameters", "KPPDriver", "KPPOutput"]
