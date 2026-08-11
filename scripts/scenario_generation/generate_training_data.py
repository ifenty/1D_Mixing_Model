"""
Generate ML training data from MITgcm output using Python KPP.

This script:
1. Reads MITgcm diagnostic output (NetCDF)
2. Extracts column data for each (time, y, x) point
3. Computes KPP mixing coefficients using Python implementation
4. Saves results in format suitable for ML training
"""

import numpy as np
import xarray as xr
from pathlib import Path
from typing import Optional, Dict, List
import argparse
import yaml
from tqdm import tqdm
import sys

# Add repo root to path to import packages
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from KPP_ML.KPP_PY.kpp_parameters import KPPParameters
from KPP_ML.KPP_PY.kpp_core_driver import KPPDriver


def resolve_shared_physical_yaml(explicit_path: str | None = None) -> Path:
    """Resolve path to shared physical_parameters.yaml."""
    if explicit_path is not None:
        return Path(explicit_path)
    return Path(__file__).resolve().parents[2] / "configuration_yamls" / "physical_parameters.yaml"


def load_physical_parameters_yaml(physical_yaml: str | None = None) -> Dict[str, float]:
    """Load shared physical constants."""
    physical_path = resolve_shared_physical_yaml(physical_yaml)
    with open(physical_path, "r") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict) or "physical_parameters" not in cfg:
        raise ValueError("physical YAML must contain top-level 'physical_parameters'")
    pp = cfg["physical_parameters"]
    if not isinstance(pp, dict):
        raise ValueError("physical_parameters must be a mapping")
    gravity = float(pp["gravity"])
    rho_const = float(pp["rho_const"])
    heat_capacity_cp = float(pp["heat_capacity_cp"])
    if gravity <= 0.0 or rho_const <= 0.0 or heat_capacity_cp <= 0.0:
        raise ValueError("gravity, rho_const, and heat_capacity_cp must be positive")
    return {
        "gravity": gravity,
        "rho_const": rho_const,
        "heat_capacity_cp": heat_capacity_cp,
    }


def _build_depth_from_drf(drF: List[float]) -> tuple[np.ndarray, np.ndarray]:
    """Build negative-downward depth centers and cell thickness from drF."""
    cell_thickness = np.asarray(drF, dtype=float)
    if cell_thickness.ndim != 1 or len(cell_thickness) == 0:
        raise ValueError("drF must be a non-empty 1D list")
    if np.any(cell_thickness <= 0.0):
        raise ValueError("all drF values must be positive")

    faces = np.zeros(len(cell_thickness) + 1, dtype=float)
    faces[1:] = -np.cumsum(cell_thickness)
    depth = 0.5 * (faces[:-1] + faces[1:])
    return depth, cell_thickness


def _load_shared_yaml_column(initial_condition_yaml: str, forcing_yaml: str) -> Dict[str, np.ndarray | float]:
    """Load shared initial condition and forcing files used by both models."""
    with open(initial_condition_yaml, "r") as f:
        ic = yaml.safe_load(f)
    with open(forcing_yaml, "r") as f:
        forcing = yaml.safe_load(f)

    if not isinstance(ic, dict) or "initial_conditions" not in ic:
        raise ValueError("initial condition YAML must contain 'initial_conditions'")
    ic_data = ic["initial_conditions"]

    if not isinstance(forcing, dict) or "atmospheric_forcing" not in forcing:
        raise ValueError("forcing YAML must contain 'atmospheric_forcing'")
    atm = forcing["atmospheric_forcing"]

    drf = ic_data.get("drF")
    if drf is None:
        raise ValueError("initial_conditions.drF is required")
    depth, cell_thickness = _build_depth_from_drf(drf)
    nz = len(cell_thickness)

    def _vec(name: str) -> np.ndarray:
        values = np.asarray(ic_data.get(name), dtype=float)
        if values.shape != (nz,):
            raise ValueError(f"initial_conditions.{name} must have length {nz}")
        return values

    return {
        "depth": depth,
        "cell_thickness": cell_thickness,
        "theta": _vec("theta"),
        "salt": _vec("salt"),
        "u_vel": _vec("u_vel"),
        "v_vel": _vec("v_vel"),
        "tau_x": float(atm.get("tau_x", 0.0)),
        "tau_y": float(atm.get("tau_y", 0.0)),
        "q_net": float(atm.get("q_net", 0.0)),
        "q_sw": float(atm.get("q_sw", 0.0)),
        "fw_flux": float(atm.get("fw_flux", 0.0)),
        "coriol": float(ic_data.get("coriol", 1.0e-4)),
    }


def compute_vertical_derivatives(field: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """
    Compute centered finite difference derivatives.

    Parameters
    ----------
    field : np.ndarray, shape (..., nz)
        Field to differentiate
    depth : np.ndarray, shape (nz,)
        Depth coordinates

    Returns
    -------
    np.ndarray
        Vertical derivative
    """
    nz = len(depth)
    deriv = np.zeros_like(field)

    # Use centered differences
    for k in range(1, nz-1):
        dz = depth[k+1] - depth[k-1]
        deriv[..., k] = (field[..., k+1] - field[..., k-1]) / dz

    # Forward/backward at boundaries
    deriv[..., 0] = (field[..., 1] - field[..., 0]) / (depth[1] - depth[0])
    deriv[..., -1] = (field[..., -1] - field[..., -2]) / (depth[-1] - depth[-2])

    return deriv


def process_mitgcm_output(
    input_path: str,
    output_path: str,
    config_path: Optional[str] = None,
    time_indices: Optional[List[int]] = None,
    spatial_stride: int = 1,
    save_diagnostics: bool = True,
    vertical_subsample: Optional[int] = None,
    initial_condition_yaml: Optional[str] = None,
    forcing_yaml: Optional[str] = None,
    physical_parameters_yaml: Optional[str] = None,
) -> None:
    """
    Process MITgcm output to generate KPP training data.

    Parameters
    ----------
    input_path : str
        Path to MITgcm NetCDF output file
    output_path : str
        Path to output NPZ file for training data
    config_path : str, optional
        Path to KPP configuration YAML
    time_indices : list of int, optional
        Time indices to process (None = all)
    spatial_stride : int
        Stride for spatial sampling (e.g., 2 = every other grid point)
    save_diagnostics : bool
        If True, save additional diagnostic fields
    vertical_subsample : int, optional
        If provided, subsample to this many vertical levels
    """
    print("=" * 70)
    print("KPP Training Data Generation")
    print("=" * 70)

    # Load configuration
    if config_path is not None:
        params = KPPParameters.from_yaml(config_path)
        print(f"\nLoaded KPP params from {config_path}")
    else:
        params = KPPParameters()
        print("\nUsing default KPP configuration")

    physical = load_physical_parameters_yaml(physical_parameters_yaml)
    params.gravity = physical["gravity"]
    params.rho_const = physical["rho_const"]
    params.heat_capacity_cp = physical["heat_capacity_cp"]
    print(f"Loaded shared physical constants from {resolve_shared_physical_yaml(physical_parameters_yaml)}")

    # Initialize KPP driver
    print("Initializing KPP driver...")
    kpp = KPPDriver(params)

    # Load MITgcm output
    print(f"\nLoading MITgcm output from {input_path}...")
    ds = xr.open_dataset(input_path)
    print(f"  Dataset dimensions: {dict(ds.dims)}")

    # Extract dimensions
    if time_indices is None:
        time_indices = range(ds.dims['T'])
    nt = len(time_indices)

    ny, nx = ds.dims.get('Y', ds.dims.get('Yp1', 1)), ds.dims.get('X', ds.dims.get('Xp1', 1))
    nz = ds.dims['Z']

    # Apply spatial stride
    y_indices = range(0, ny, spatial_stride)
    x_indices = range(0, nx, spatial_stride)

    print(f"  Processing {nt} time steps, {len(y_indices)} y points, {len(x_indices)} x points")

    use_shared_yaml = initial_condition_yaml is not None and forcing_yaml is not None

    # Get vertical grid
    if use_shared_yaml:
        shared = _load_shared_yaml_column(initial_condition_yaml, forcing_yaml)
        depth = shared["depth"]
        cell_thickness = shared["cell_thickness"]
        nz = len(depth)
        print("  Using shared YAML IC/forcing for all processed samples")
        print(f"    IC file: {initial_condition_yaml}")
        print(f"    forcing file: {forcing_yaml}")
    else:
        if 'Z' in ds.coords:
            depth = ds['Z'].values
        elif 'RC' in ds:
            depth = ds['RC'].values
        else:
            raise ValueError("Cannot find depth coordinate (Z or RC)")

        # Cell thickness
        if 'drF' in ds:
            cell_thickness = ds['drF'].values
        else:
            # Compute from depth
            cell_thickness = np.zeros(nz)
            cell_thickness[0] = -2 * depth[0]
            for k in range(1, nz):
                cell_thickness[k] = depth[k-1] - depth[k]

    # Vertical subsampling
    if vertical_subsample is not None and vertical_subsample < nz:
        print(f"  Subsampling vertically: {nz} -> {vertical_subsample} levels")
        k_indices = np.linspace(0, nz-1, vertical_subsample, dtype=int)
        depth = depth[k_indices]
        cell_thickness = cell_thickness[k_indices]
        nz = vertical_subsample
        if use_shared_yaml:
            for key in ("theta", "salt", "u_vel", "v_vel"):
                shared[key] = shared[key][k_indices]
    else:
        k_indices = None

    print(f"  Vertical grid: {nz} levels, {depth[0]:.1f} to {depth[-1]:.1f} m")

    # Storage for training data
    samples = []
    n_samples = nt * len(y_indices) * len(x_indices)
    print(f"\n  Total samples to process: {n_samples}")

    # Process columns
    n_processed = 0
    n_skipped = 0

    with tqdm(total=n_samples, desc="Processing columns") as pbar:
        for t in time_indices:
            for j in y_indices:
                for i in x_indices:
                    # Extract column data
                    if use_shared_yaml:
                        theta = shared["theta"]
                        salt = shared["salt"]
                        u_vel = shared["u_vel"]
                        v_vel = shared["v_vel"]
                    elif k_indices is not None:
                        theta = ds['THETA'][t, k_indices, j, i].values
                        salt = ds['SALT'][t, k_indices, j, i].values
                        u_vel = ds['UVEL'][t, k_indices, j, i].values if 'UVEL' in ds else np.zeros(nz)
                        v_vel = ds['VVEL'][t, k_indices, j, i].values if 'VVEL' in ds else np.zeros(nz)
                    else:
                        theta = ds['THETA'][t, :, j, i].values
                        salt = ds['SALT'][t, :, j, i].values
                        u_vel = ds['UVEL'][t, :, j, i].values if 'UVEL' in ds else np.zeros(nz)
                        v_vel = ds['VVEL'][t, :, j, i].values if 'VVEL' in ds else np.zeros(nz)

                    # Check for valid data
                    if not (np.isfinite(theta).all() and np.isfinite(salt).all()):
                        n_skipped += 1
                        pbar.update(1)
                        continue

                    # Surface forcing
                    if use_shared_yaml:
                        tau_x = shared["tau_x"]
                        tau_y = shared["tau_y"]
                        q_net = shared["q_net"]
                        q_sw = shared["q_sw"]
                        fw_flux = shared["fw_flux"]
                    else:
                        tau_x = ds['oceTAUX'][t, j, i].values if 'oceTAUX' in ds else 0.1
                        tau_y = ds['oceTAUY'][t, j, i].values if 'oceTAUY' in ds else 0.0
                        q_net = ds['oceQnet'][t, j, i].values if 'oceQnet' in ds else 0.0
                        q_sw = ds['oceQsw'][t, j, i].values if 'oceQsw' in ds else 0.0
                        fw_flux = ds.get('oceFWflx', xr.DataArray(np.zeros((nt, ny, nx))))[t, j, i].values

                    # Coriolis (approximate from latitude if available)
                    if use_shared_yaml:
                        coriol = shared["coriol"]
                    elif 'YC' in ds:
                        lat = ds['YC'][j, i].values
                        coriol = 2 * 7.2921e-5 * np.sin(np.deg2rad(lat))
                    else:
                        coriol = 1.0e-4  # Default mid-latitude

                    # Convert wind stress to m^2/s^2 if needed
                    if np.abs(tau_x) > 10:  # Likely in N/m^2
                        tau_x /= params.rho_const
                        tau_y /= params.rho_const

                    try:
                        # Compute KPP mixing
                        output = kpp.compute_mixing(
                            theta=theta,
                            salt=salt,
                            u_vel=u_vel,
                            v_vel=v_vel,
                            depth=depth,
                            cell_thickness=cell_thickness,
                            tau_x=tau_x,
                            tau_y=tau_y,
                            q_net=q_net,
                            q_sw=q_sw,
                            fw_flux=fw_flux,
                            coriol=coriol,
                        )

                        # Compute derived features
                        dtheta_dz = compute_vertical_derivatives(theta, depth)
                        dsalt_dz = compute_vertical_derivatives(salt, depth)
                        du_dz = compute_vertical_derivatives(u_vel, depth)
                        dv_dz = compute_vertical_derivatives(v_vel, depth)
                        shear_sq = du_dz**2 + dv_dz**2

                        # Store sample
                        sample = {
                            # Metadata
                            'time': t,
                            'y': j,
                            'x': i,
                            # State variables
                            'theta': theta.astype(np.float32),
                            'salt': salt.astype(np.float32),
                            'u_vel': u_vel.astype(np.float32),
                            'v_vel': v_vel.astype(np.float32),
                            # Derivatives
                            'dtheta_dz': dtheta_dz.astype(np.float32),
                            'dsalt_dz': dsalt_dz.astype(np.float32),
                            'du_dz': du_dz.astype(np.float32),
                            'dv_dz': dv_dz.astype(np.float32),
                            'shear_sq': shear_sq.astype(np.float32),
                            # Surface forcing
                            'tau_x': float(tau_x),
                            'tau_y': float(tau_y),
                            'tau_mag': float(np.sqrt(tau_x**2 + tau_y**2)),
                            'q_net': float(q_net),
                            'q_sw': float(q_sw),
                            # KPP outputs (targets)
                            'KPPviscAz': output.visc_az.astype(np.float32),
                            'KPPdiffKzS': output.diff_kz_s.astype(np.float32),
                            'KPPdiffKzT': output.diff_kz_t.astype(np.float32),
                            'KPPghat': output.ghat.astype(np.float32),
                            'KPPhbl': float(output.hbl),
                        }

                        if save_diagnostics:
                            sample.update({
                                'KPPustar': float(output.ustar),
                                'KPPbfsfc': float(output.bfsfc),
                            })

                        samples.append(sample)
                        n_processed += 1

                    except Exception as e:
                        print(f"\nError at (t={t}, y={j}, x={i}): {e}")
                        n_skipped += 1

                    pbar.update(1)

    print(f"\nProcessed {n_processed} samples, skipped {n_skipped}")

    # Convert to arrays
    print("\nConverting to arrays...")
    data = {}

    # Stack all samples
    for key in samples[0].keys():
        if isinstance(samples[0][key], np.ndarray):
            # Profile data
            data[key] = np.stack([s[key] for s in samples])
        else:
            # Scalar data
            data[key] = np.array([s[key] for s in samples])

    # Add metadata
    data['depth'] = depth.astype(np.float32)
    data['cell_thickness'] = cell_thickness.astype(np.float32)
    data['config'] = str(config)

    # Save
    print(f"\nSaving to {output_path}...")
    np.savez_compressed(output_path, **data)

    # Print statistics
    print("\n" + "=" * 70)
    print("Data Statistics")
    print("=" * 70)
    print(f"Total samples: {len(samples)}")
    print(f"Vertical levels: {nz}")
    print(f"\nKPPhbl range: {data['KPPhbl'].min():.1f} to {data['KPPhbl'].max():.1f} m")
    print(f"KPPdiffKzS range: {data['KPPdiffKzS'].min():.2e} to {data['KPPdiffKzS'].max():.2e} m^2/s")
    print(f"Temperature range: {data['theta'].min():.2f} to {data['theta'].max():.2f} °C")
    print(f"Salinity range: {data['salt'].min():.2f} to {data['salt'].max():.2f} psu")

    print("\n" + "=" * 70)
    print("Training data generation complete!")
    print("=" * 70)


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Generate KPP training data from MITgcm output"
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to MITgcm NetCDF diagnostic file"
    )
    parser.add_argument(
        "output",
        type=str,
        help="Path to output NPZ file"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to KPP configuration YAML (default: use defaults)"
    )
    parser.add_argument(
        "--time-indices",
        type=int,
        nargs="+",
        default=None,
        help="Time indices to process (default: all)"
    )
    parser.add_argument(
        "--spatial-stride",
        type=int,
        default=1,
        help="Spatial sampling stride (default: 1 = all points)"
    )
    parser.add_argument(
        "--vertical-subsample",
        type=int,
        default=None,
        help="Subsample to N vertical levels (default: use all)"
    )
    parser.add_argument(
        "--no-diagnostics",
        action="store_true",
        help="Skip saving diagnostic fields"
    )
    parser.add_argument(
        "--initial-condition-yaml",
        type=str,
        default=None,
        help="Path to shared initial condition YAML (applied to all samples)"
    )
    parser.add_argument(
        "--forcing-yaml",
        type=str,
        default=None,
        help="Path to shared atmospheric forcing YAML (applied to all samples)"
    )
    parser.add_argument(
        "--physical-parameters-yaml",
        type=str,
        default=None,
        help="Path to shared physical_parameters.yaml"
    )

    args = parser.parse_args()

    if (args.initial_condition_yaml is None) ^ (args.forcing_yaml is None):
        parser.error("--initial-condition-yaml and --forcing-yaml must be provided together")

    process_mitgcm_output(
        input_path=args.input,
        output_path=args.output,
        config_path=args.config,
        time_indices=args.time_indices,
        spatial_stride=args.spatial_stride,
        save_diagnostics=not args.no_diagnostics,
        vertical_subsample=args.vertical_subsample,
        initial_condition_yaml=args.initial_condition_yaml,
        forcing_yaml=args.forcing_yaml,
        physical_parameters_yaml=args.physical_parameters_yaml,
    )


if __name__ == "__main__":
    main()
