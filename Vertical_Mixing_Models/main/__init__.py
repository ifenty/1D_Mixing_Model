"""
Unified 1D ocean column model driver.

Provides infrastructure for running 1D mixing experiments with different
parameterizations (KPP, GGL90, etc.) using a common interface.
"""

from .column_grid import ColumnGrid
from .column_state import ColumnState
from .config_manager import ConfigManager
from .mixing_adapter import (
    MixingOutput,
    MixingSchemeAdapter,
    KPPAdapter,
    GGL90Adapter
)
from .unified_driver import UnifiedColumnDriver
from .diagnostics import DiagnosticsManager

__all__ = [
    'ColumnGrid',
    'ColumnState',
    'ConfigManager',
    'MixingOutput',
    'MixingSchemeAdapter',
    'KPPAdapter',
    'GGL90Adapter',
    'UnifiedColumnDriver',
    'DiagnosticsManager',
]
