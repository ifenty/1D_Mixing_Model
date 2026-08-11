#!/usr/bin/env python3
"""
Example script for running 1D mixing experiments with unified driver.

Demonstrates how to run experiments with either KPP or GGL90 using the same
configuration and driver infrastructure. Supports parameter overrides via
scheme-specific YAML files and other tuning options.

Usage:
    python run_experiment_example.py
    python run_experiment_example.py --scheme kpp
    python run_experiment_example.py --kpp-yaml path/to/kpp.yaml
    python run_experiment_example.py --ggl90-yaml path/to/ggl90.yaml
    python run_experiment_example.py --ivdc-kappa 10.0
    python run_experiment_example.py --no-plots
"""

import os
from pathlib import Path
import argparse

# ---------------------------------------------------------------------------
# Paths. This file lives in <repo>/1D_Mixing_Model/main/.
# ---------------------------------------------------------------------------
PKG_DIR = Path(__file__).resolve().parent.parent          # 1D_Mixing_Model/
CONFIG_DIR = PKG_DIR / "configuration_yamls"
PHYSICAL_YAML = CONFIG_DIR / "physical_parameters.yaml"

# KPP reads the shared physical constants from this env var at import time.
os.environ['KPP_PHYSICAL_PARAMETERS_YAML'] = str(PHYSICAL_YAML)

# Make the package importable.
import sys
sys.path.insert(0, str(PKG_DIR))

from main import (  # noqa: E402
    UnifiedColumnDriver,
    ConfigManager,
    KPPAdapter,
    GGL90Adapter,
)
from KPP.kpp_core_driver import KPPDriver  # noqa: E402
from KPP.kpp_parameters import KPPParameters  # noqa: E402
from GGL90.ggl90_core_driver import GGL90Driver  # noqa: E402
from GGL90.ggl90_parameters import GGL90Parameters  # noqa: E402


def run_one(
    scheme: str,
    config_dir: Path,
    output_dir: Path,
    kpp_yaml: Path | None = None,
    ggl90_yaml: Path | None = None,
    ivdc_kappa: float | None = None,
):
    """Run a single experiment with a single scheme; write <scheme>_experiment.npz."""
    config_mgr = ConfigManager(config_dir)
    physical = config_mgr.load_physical_parameters()
    if ivdc_kappa is not None:
        physical['ivdc_kappa'] = ivdc_kappa

    if scheme == "kpp":
        # Built-in defaults first, then optional KPP-specific overrides.
        params = KPPParameters.from_yaml(kpp_yaml)
        adapter = KPPAdapter(
            KPPDriver(params),
            background_visc=physical['background_viscosity'],
            background_diff=physical['background_diffusivity'],
        )
    elif scheme == "ggl90":
        # Built-in defaults first, then optional GGL90-specific overrides.
        params = GGL90Parameters.from_yaml(ggl90_yaml)
        adapter = GGL90Adapter(GGL90Driver(params), physical)
    else:
        raise ValueError(f"unknown scheme {scheme!r}")

    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    out_path = output_dir / f"{scheme}_experiment.npz"
    results = driver.run_experiment(output_path=out_path)
    return out_path, results


def make_plots(npz_path: Path, out_dir: Path, scheme: str, n_profiles: int = 5):
    """Generate profile + contour PNGs for one output file into out_dir."""
    # Imported lazily so a --no-plots run needs no matplotlib.
    from main.unified_plotter import make_figures

    fig1, fig2 = make_figures(npz_path, n_profiles=n_profiles)
    p1 = out_dir / f"{scheme}_profiles.png"
    p2 = out_dir / f"{scheme}_contours.png"
    fig1.savefig(p1, dpi=150, bbox_inches="tight")
    fig2.savefig(p2, dpi=150, bbox_inches="tight")
    # Close to avoid accumulating open figures across many scenarios.
    import matplotlib.pyplot as plt
    plt.close(fig1)
    plt.close(fig2)
    return p1, p2


def main():
    parser = argparse.ArgumentParser(
        description="Run 1D mixing experiments with unified driver (KPP and/or GGL90)"
    )
    parser.add_argument(
        "--scheme", choices=["kpp", "ggl90", "both"], default="both",
        help="Which mixing scheme(s) to run (default: both).",
    )
    parser.add_argument(
        "--config-dir", type=Path, default=CONFIG_DIR,
        help=(
            "Directory containing YAML configuration files "
            f"(default: {CONFIG_DIR})."
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help=f"Directory for output files (default: {PKG_DIR / 'output'}).",
    )
    parser.add_argument(
        "--n-profiles", type=int, default=5,
        help="Number of equally-spaced profile times per plot (default 5).",
    )
    parser.add_argument(
        "--no-plots", action="store_true", help="Skip figure generation.",
    )
    parser.add_argument(
        "--kpp-yaml", type=Path,
        help="Optional KPP parameter YAML; its keys override KPP defaults.",
    )
    parser.add_argument(
        "--ggl90-yaml", type=Path,
        help="Optional GGL90 parameter YAML; its keys override GGL90 defaults.",
    )
    parser.add_argument(
        "--ivdc-kappa", type=float, default=None,
        help=(
            "Override the shared physical_parameters.yaml convective-"
            "adjustment diffusivity (MITgcm's ivdc_kappa) for this run "
            "[m^2/s]. Default: use the value from physical_parameters.yaml "
            "(0.0 unless set). ECCOv4 Release 4 uses ivdc_kappa=10."
        ),
    )
    args = parser.parse_args()

    # Resolve paths
    args.config_dir = args.config_dir.expanduser().resolve()
    if args.output_dir is None:
        args.output_dir = PKG_DIR / "output"
    args.output_dir = args.output_dir.expanduser().resolve()

    # Validate config directory
    if not args.config_dir.is_dir():
        parser.error(f"config-dir must be a directory: {args.config_dir}")

    # Headless rendering for the batch run.
    if not args.no_plots:
        import matplotlib
        matplotlib.use("Agg")

    # Validate scheme-specific YAML files
    for option_name in ("kpp_yaml", "ggl90_yaml"):
        yaml_path = getattr(args, option_name)
        if yaml_path is not None:
            yaml_path = yaml_path.expanduser().resolve()
            if not yaml_path.is_file():
                parser.error(f"--{option_name.replace('_', '-')} must name a file: {yaml_path}")
            setattr(args, option_name, yaml_path)

    if args.kpp_yaml is not None and "kpp" not in args.scheme and args.scheme != "both":
        parser.error("--kpp-yaml requires --scheme kpp or --scheme both")
    if args.ggl90_yaml is not None and "ggl90" not in args.scheme and args.scheme != "both":
        parser.error("--ggl90-yaml requires --scheme ggl90 or --scheme both")

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Print configuration
    print(f"Config directory    : {args.config_dir}")
    print(f"Output directory    : {args.output_dir}")
    print(f"Schemes             : {args.scheme}")
    print(f"KPP YAML override   : {args.kpp_yaml or 'built-in defaults'}")
    print(f"GGL90 YAML override : {args.ggl90_yaml or 'built-in defaults'}")
    print(f"ivdc_kappa override : {args.ivdc_kappa if args.ivdc_kappa is not None else 'physical_parameters.yaml default'}")
    print("=" * 70)

    schemes = ["kpp", "ggl90"] if args.scheme == "both" else [args.scheme]
    summary = []

    for scheme in schemes:
        print(f"\n--- {scheme.upper()} ---")
        npz_path, results = run_one(
            scheme, args.config_dir, args.output_dir,
            args.kpp_yaml, args.ggl90_yaml,
            ivdc_kappa=args.ivdc_kappa,
        )
        fst = results["final_state"]
        row = {
            "scheme": scheme,
            "sst": float(fst.theta[0]),
            "sss": float(fst.salt[0]),
        }
        summary.append(row)

        print(f"  Final SST: {fst.theta[0]:.3f}°C")
        print(f"  Final SSS: {fst.salt[0]:.3f}psu")
        if scheme == "ggl90":
            print(f"  Final surface TKE: {fst.prognostic_vars['tke'][0]:.6e} m²/s²")

        if not args.no_plots:
            p1, p2 = make_plots(npz_path, args.output_dir, scheme,
                                n_profiles=args.n_profiles)
            print(f"  plots: {p1.name}, {p2.name}")

    # Final summary table.
    print("\n" + "=" * 70)
    print("SUMMARY (final surface values)")
    print("=" * 70)
    print(f"{'scheme':<8}{'SST [°C]':>12}{'SSS [psu]':>12}")
    for r in summary:
        print(f"{r['scheme']:<8}{r['sst']:>12.3f}{r['sss']:>12.3f}")


if __name__ == '__main__':
    main()
