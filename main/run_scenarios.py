#!/usr/bin/env python3
"""
Run every distinct scenario in simulations/scenarios/ with both mixing schemes
(KPP and GGL90), and write each scenario's output + plots to its own
subdirectory of the top-level output/ folder.

Scenario layout (in simulations/scenarios/):
    scenario_<name>_initial_conditions.yaml
    scenario_<name>_atmospheric_forcing.yaml
    scenario_<name>_time_integration.yaml
The shared physical_parameters.yaml lives in 1D_Mixing_Model/configuration_yamls/
and is NOT scenario-specific.

Output layout (created under <repo>/output/):
    output/<name>/kpp_experiment.npz
    output/<name>/ggl90_experiment.npz
    output/<name>/kpp_profiles.png,  kpp_contours.png
    output/<name>/ggl90_profiles.png, ggl90_contours.png

Usage:
    python 1D_Mixing_Model/main/run_scenarios.py
    python 1D_Mixing_Model/main/run_scenarios.py --output-dir /path/to/output
    python 1D_Mixing_Model/main/run_scenarios.py --scheme kpp
    python 1D_Mixing_Model/main/run_scenarios.py --scenario calm_baseline hurricane_wind
    python 1D_Mixing_Model/main/run_scenarios.py --ggl90-yaml path/to/ggl90.yaml
    python 1D_Mixing_Model/main/run_scenarios.py --kpp-yaml path/to/kpp.yaml
    python 1D_Mixing_Model/main/run_scenarios.py --no-plots
"""

import os
import re
import argparse
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Paths. This file lives in <repo>/1D_Mixing_Model/main/. The scenarios are
# in 1D_Mixing_Model/simulations/scenarios/. Output goes to parent dir.
# ---------------------------------------------------------------------------
PKG_DIR = Path(__file__).resolve().parent.parent          # 1D_Mixing_Model/
REPO_DIR = PKG_DIR.parent                                  # 1D_Mixing_Experiments/
SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
OUTPUT_DIR = REPO_DIR / "output"
CONFIG_DIR = PKG_DIR / "configuration_yamls"
PHYSICAL_YAML = CONFIG_DIR / "physical_parameters.yaml"

# KPP reads the shared physical constants from this env var at import time.
os.environ["KPP_PHYSICAL_PARAMETERS_YAML"] = str(PHYSICAL_YAML)

# Make the package importable (so `from main import ...` works when this script
# is run directly).
import sys
sys.path.insert(0, str(PKG_DIR))

from main import (  # noqa: E402
    UnifiedColumnDriver,
    ConfigManager,
    KPPAdapter,
    GGL90Adapter,
)
from KPP_ML.KPP_PY.kpp_core_driver import KPPDriver  # noqa: E402
from KPP_ML.KPP_PY.kpp_parameters import KPPParameters  # noqa: E402
from GGL90_ML.GGL90_PY.ggl90_core_driver import GGL90Driver  # noqa: E402
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters  # noqa: E402


def discover_scenarios() -> List[str]:
    """Return the sorted list of distinct scenario names in SCENARIO_DIR.

    A scenario is "complete" only if all three of its config files exist.
    """
    pat = re.compile(r"^scenario_(.+)_initial_conditions\.yaml$")
    names = []
    for f in SCENARIO_DIR.glob("scenario_*_initial_conditions.yaml"):
        m = pat.match(f.name)
        if not m:
            continue
        name = m.group(1)
        forcing = SCENARIO_DIR / f"scenario_{name}_atmospheric_forcing.yaml"
        timing = SCENARIO_DIR / f"scenario_{name}_time_integration.yaml"
        if forcing.exists() and timing.exists():
            names.append(name)
        else:
            print(f"  [skip] {name}: missing forcing/time_integration file")
    return sorted(names)


def _config_manager_for(name: str) -> ConfigManager:
    """ConfigManager pointed at the scenario files (prefixed) + shared physics."""
    return ConfigManager(
        config_dir=SCENARIO_DIR,
        prefix=f"scenario_{name}_",
        physical_params_path=PHYSICAL_YAML,
    )


def run_one(
    name: str,
    scheme: str,
    out_dir: Path,
    kpp_yaml: Path | None = None,
    ggl90_yaml: Path | None = None,
    ivdc_kappa: float | None = None,
):
    """Run a single scenario with a single scheme; write <scheme>_experiment.npz."""
    config_mgr = _config_manager_for(name)
    physical = config_mgr.load_physical_parameters()
    if ivdc_kappa is not None:
        physical['ivdc_kappa'] = ivdc_kappa

    if scheme == "kpp":
        # Built-in defaults first, then optional data.kpp-style overrides.
        params = KPPParameters.from_yaml(kpp_yaml)
        adapter = KPPAdapter(
            KPPDriver(params),
            background_visc=physical['background_viscosity'],
            background_diff=physical['background_diffusivity'],
        )
    elif scheme == "ggl90":
        # Built-in defaults first, then optional data.ggl90-style overrides.
        params = GGL90Parameters.from_yaml(ggl90_yaml)
        adapter = GGL90Adapter(GGL90Driver(params), physical)
    else:
        raise ValueError(f"unknown scheme {scheme!r}")

    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    out_path = out_dir / f"{scheme}_experiment.npz"
    results = driver.run_experiment(output_path=out_path)
    return out_path, results


def clear_previous_outputs(out_dir: Path) -> List[Path]:
    """Remove generated artifacts from a selected scenario's output directory."""
    removed = []
    for pattern in ("*.npz", "*.png"):
        for output_path in out_dir.glob(pattern):
            output_path.unlink()
            removed.append(output_path)
    return removed


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
        description="Run all scenarios (both schemes) and plot their output."
    )
    parser.add_argument(
        "--scheme", choices=["kpp", "ggl90", "both"], default="both",
        help="Which mixing scheme(s) to run per scenario (default: both).",
    )
    parser.add_argument(
        "--scenario", nargs="+", default=None,
        help="Only run these scenario name(s). Default: all discovered scenarios.",
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
        "--output-dir", type=Path, default=OUTPUT_DIR,
        help=(
            "Output directory root for per-scenario subfolders "
            f"(default: {OUTPUT_DIR})."
        ),
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

    args.output_dir = args.output_dir.expanduser().resolve()

    # Headless rendering for the batch run.
    if not args.no_plots:
        import matplotlib
        matplotlib.use("Agg")

    all_scenarios = discover_scenarios()
    if args.scenario:
        unknown = [s for s in args.scenario if s not in all_scenarios]
        if unknown:
            raise SystemExit(
                f"Unknown scenario(s): {unknown}. Available: {all_scenarios}"
            )
        scenarios = args.scenario
    else:
        scenarios = all_scenarios

    schemes = ["kpp", "ggl90"] if args.scheme == "both" else [args.scheme]

    for option_name in ("kpp_yaml", "ggl90_yaml"):
        yaml_path = getattr(args, option_name)
        if yaml_path is not None:
            yaml_path = yaml_path.expanduser().resolve()
            if not yaml_path.is_file():
                parser.error(f"--{option_name.replace('_', '-')} must name a file: {yaml_path}")
            setattr(args, option_name, yaml_path)

    if args.kpp_yaml is not None and "kpp" not in schemes:
        parser.error("--kpp-yaml requires --scheme kpp or --scheme both")
    if args.ggl90_yaml is not None and "ggl90" not in schemes:
        parser.error("--ggl90-yaml requires --scheme ggl90 or --scheme both")

    print(f"Scenarios directory : {SCENARIO_DIR}")
    print(f"Output directory    : {args.output_dir}")
    print(f"Scenarios to run    : {scenarios}")
    print(f"Schemes             : {schemes}")
    print(f"KPP YAML override   : {args.kpp_yaml or 'built-in defaults'}")
    print(f"GGL90 YAML override : {args.ggl90_yaml or 'built-in defaults'}")
    print(f"ivdc_kappa override : {args.ivdc_kappa if args.ivdc_kappa is not None else 'physical_parameters.yaml default'}")
    print("=" * 70)

    summary = []
    for name in scenarios:
        out_dir = args.output_dir / name
        out_dir.mkdir(parents=True, exist_ok=True)
        removed = clear_previous_outputs(out_dir)
        print(f"\n### Scenario: {name}  ->  {out_dir}")
        if removed:
            print(f"  removed {len(removed)} old output file(s)")
        for scheme in schemes:
            print(f"\n--- {scheme.upper()} : {name} ---")
            npz_path, results = run_one(
                name, scheme, out_dir, args.kpp_yaml, args.ggl90_yaml,
                ivdc_kappa=args.ivdc_kappa,
            )
            fst = results["final_state"]
            row = {
                "scenario": name, "scheme": scheme,
                "sst": float(fst.theta[0]), "sss": float(fst.salt[0]),
            }
            summary.append(row)
            if not args.no_plots:
                p1, p2 = make_plots(npz_path, out_dir, scheme,
                                    n_profiles=args.n_profiles)
                print(f"  plots: {p1.name}, {p2.name}")

    # Final summary table.
    print("\n" + "=" * 70)
    print("SUMMARY (final surface values)")
    print("=" * 70)
    print(f"{'scenario':<28}{'scheme':<8}{'SST [°C]':>12}{'SSS [psu]':>12}")
    for r in summary:
        print(f"{r['scenario']:<28}{r['scheme']:<8}"
              f"{r['sst']:>12.3f}{r['sss']:>12.3f}")


if __name__ == "__main__":
    main()
