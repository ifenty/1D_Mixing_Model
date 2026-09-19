"""
Configuration manager for loading YAML files.

Loads physical parameters, initial conditions, forcing, and time-stepping configuration
from YAML files in the configuration_yamls directory.
"""

from pathlib import Path
from typing import Dict, Any
import yaml


class ConfigManager:
    """
    Manages loading and accessing configuration from YAML files.

    Args:
        config_dir: Path to directory containing the initial-conditions,
            atmospheric-forcing, and time-integration YAML files.
        prefix: Optional filename prefix, e.g. "scenario_calm_baseline_", so
            that files named "<prefix>initial_conditions.yaml" etc. are loaded.
            Defaults to "" (the standard unprefixed filenames).
        physical_params_path: Optional explicit path to physical_parameters.yaml.
            Scenario directories don't carry their own copy, so callers can point
            at the shared configuration_yamls/physical_parameters.yaml. Defaults
            to "<config_dir>/physical_parameters.yaml".
    """

    def __init__(self, config_dir: Path, prefix: str = "",
                 physical_params_path: Path = None):
        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
        self.prefix = prefix
        self.physical_params_path = (
            Path(physical_params_path) if physical_params_path is not None
            else self.config_dir / 'physical_parameters.yaml'
        )

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load and parse a YAML file (applying the configured prefix)."""
        filepath = self.config_dir / f"{self.prefix}{filename}"
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        with open(filepath, 'r') as f:
            return yaml.safe_load(f)

    def load_physical_parameters(self) -> Dict[str, float]:
        """
        Load physical constants from physical_parameters.yaml.

        This file is shared (not scenario-specific), so it is read from
        `physical_params_path` and is NOT affected by the scenario prefix.

        Returns:
            Dictionary with keys: gravity, rho_const, heat_capacity_cp,
            background_viscosity, background_diffusivity
        """
        with open(self.physical_params_path, 'r') as f:
            data = yaml.safe_load(f)
        return data['physical_parameters']

    def load_initial_conditions(self) -> Dict[str, Any]:
        """
        Load initial conditions from initial_conditions.yaml.

        Returns:
            Dictionary with keys: drF, theta, salt, u_vel, v_vel, coriol
        """
        data = self._load_yaml('initial_conditions.yaml')
        return data['initial_conditions']

    def load_atmospheric_forcing(self) -> Dict[str, float]:
        """
        Load atmospheric forcing from atmospheric_forcing.yaml.

        Returns:
            Dictionary with keys: tau_x, tau_y, q_net, q_sw, fw_flux, rho_water
        """
        data = self._load_yaml('atmospheric_forcing.yaml')
        return data['atmospheric_forcing']

    def load_time_integration(self) -> Dict[str, int]:
        """
        Load time-stepping parameters from time_integration.yaml.

        Returns:
            Dictionary with keys: dt_seconds, n_steps, output_frequency_steps
        """
        data = self._load_yaml('time_integration.yaml')
        return data['time_integration']

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all configuration files at once.

        Returns:
            Dictionary with keys: physical, initial, forcing, time
        """
        return {
            'physical': self.load_physical_parameters(),
            'initial': self.load_initial_conditions(),
            'forcing': self.load_atmospheric_forcing(),
            'time': self.load_time_integration(),
        }
