"""
GGL90: Python Implementation of GGL90 Vertical Mixing

A Python implementation of the GGL90 turbulent kinetic energy (TKE) mixing
scheme as used in MITgcm and ECCOv4.

Main modules (refactored for code clarity and reuse):
    - ggl90_parameters: Parameter configuration
    - ggl90_scheme_specific: GGL90-specific logic (mixing length, TKE budget)
    - ggl90_mixing_coefficients: Viscosity/diffusivity computation
    - ggl90_core_driver: Core GGL90 driver orchestration
    
Imports from main.physics_basis:
    - compute_buoyancy_frequency_squared
    - compute_vertical_shear_squared
    - etc. (shared with all schemes)

Example:
    >>> from ggl90_parameters import GGL90Parameters
    >>> from ggl90_core_driver import GGL90Driver
    >>>
    >>> # defaults only, or overlay a user override YAML:
    >>> params = GGL90Parameters.from_yaml("configuration_yamls/ggl90_eccov4r4.yaml")
    >>> ggl90 = GGL90Driver(params)
"""

__version__ = "2.0.0"
__author__ = "Based on MITgcm GGL90 package"

from .ggl90_parameters import GGL90Parameters
from .ggl90_core_driver import GGL90Driver, GGL90Output
from .ggl90_scheme_specific import GGL90MixingLength

__all__ = ['GGL90Parameters', 'GGL90Driver', 'GGL90Output', 'GGL90MixingLength']
