"""
Generate shared initial-condition + atmospheric-forcing YAML pairs for every
scenario defined in KPP_PY/extreme_scenarios.py.

The point of these YAMLs is reproducibility ACROSS codebases: the same file
pair can be fed to both KPP_PY (example_usage.py / generate_training_data.py)
and GGL90_PY (example_1d_column.py), which share the identical
`initial_conditions` + `atmospheric_forcing` schema and rebuild the vertical
grid from `drF` in exactly the same way.

This script is the single source of truth for the scenario YAMLs: it imports
the actual SCENARIOS dict and the grid / initial-profile / wind-stress
functions from extreme_scenarios.py, so the emitted files are guaranteed to
match what extreme_scenarios.py itself simulates. If a scenario changes there,
re-run this script to regenerate the YAMLs.

Output (in this shared_yaml/ directory), one triple per scenario:
    scenario_<name>_initial_conditions.yaml
    scenario_<name>_atmospheric_forcing.yaml
    scenario_<name>_time_integration.yaml

The time-integration file carries the scenario-specific n_steps, derived from
that scenario's duration (SCENARIOS[...]["hours"]) and the timestep, so each
scenario runs for its intended length in both KPP_PY and GGL90_PY. This mirrors
extreme_scenarios.py's own n_steps = round(hours*3600/dt).

Usage:
    python3 generate_extreme_scenario_yamls.py
    python3 generate_extreme_scenario_yamls.py --nz 50 --depth-max 400 --coriol 1.0e-4
    python3 generate_extreme_scenario_yamls.py --dt 600 --output-every 6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

# Make the KPP_PY package importable (shared_yaml/ is a sibling of KPP_PY/).
_KPP_ML_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KPP_ML_DIR))

from KPP_PY.extreme_scenarios import (  # noqa: E402
    SCENARIOS,
    build_stretched_grid,
    initial_profile,
    wind_stress_from_speed,
)
from KPP_PY.constants import KPPConstants  # noqa: E402


def _round_list(arr, ndigits):
    """Convert a numpy array to a plain list of rounded Python floats.

    Rounding keeps the YAML human-readable; the precision retained (see the
    per-field choices below) is far finer than any physical uncertainty and
    reproduces the profiles to well within solver tolerance.
    """
    return [float(round(float(x), ndigits)) for x in arr]


class _FlowList(list):
    """A list subclass rendered inline (flow style) in YAML for readability."""


def _flow_list_representer(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


yaml.add_representer(_FlowList, _flow_list_representer)


def build_initial_conditions_doc(name: str, forcing: dict, nz: int,
                                 depth_max: float, coriol: float) -> dict:
    """Build the initial_conditions YAML document for one scenario.

    Uses the EXACT grid and initial T/S profile that extreme_scenarios.py uses
    (build_stretched_grid + initial_profile with the scenario's mld0). Velocity
    starts at rest, matching run_scenario (u_vel = v_vel = 0).
    """
    depth, thickness = build_stretched_grid(nz, depth_max)
    theta, salt = initial_profile(depth, mld0=forcing["mld0"])
    u_vel = np.zeros(nz)
    v_vel = np.zeros(nz)

    return {
        "metadata": {
            "name": f"scenario_{name}_ic",
            "description": (
                f"Initial conditions for extreme scenario '{name}': "
                f"{forcing['label']}. Shared by KPP_PY and GGL90_PY."
            ),
            "source": "generated from KPP_PY/extreme_scenarios.py",
            "scenario": name,
            "conventions": {
                "depth_sign": "negative_downward_cell_centers",
                "velocity_units": "m_s",
                "salinity_units": "psu",
                "grid": "geometric surface-refined (build_stretched_grid)",
                "initial_mld_m": float(forcing["mld0"]),
            },
        },
        "initial_conditions": {
            # Cell thicknesses [m]; sum(drF) = depth_max, len(drF) = nz.
            "drF": _FlowList(_round_list(thickness, 6)),
            # Profiles ordered surface -> deepest.
            "theta": _FlowList(_round_list(theta, 4)),
            "salt": _FlowList(_round_list(salt, 4)),
            "u_vel": _FlowList(_round_list(u_vel, 4)),
            "v_vel": _FlowList(_round_list(v_vel, 4)),
            # Scalar consumed by KPP_PY, ignored by GGL90_PY.
            "coriol": float(coriol),
        },
    }


def build_forcing_doc(name: str, forcing: dict) -> dict:
    """Build the atmospheric_forcing YAML document for one scenario.

    Maps the scenario's forcing to the shared schema. Wind speed U10 is
    converted to kinematic wind stress tau_x = tau/rho_water via the SAME
    wind_stress_from_speed() used in run_scenario (tau_y = 0). rho_water is the
    shared single-source-of-truth reference density; GGL90_PY uses it to
    reconstruct dynamic wind stress from tau_x, so both codebases see the same
    momentum forcing.
    """
    rho_water = KPPConstants.RHO_CONST
    tau_x = wind_stress_from_speed(forcing["U10"], rho_water=rho_water)

    return {
        "metadata": {
            "name": f"scenario_{name}_forcing",
            "description": (
                f"Atmospheric forcing for extreme scenario '{name}': "
                f"{forcing['label']}. Shared by KPP_PY and GGL90_PY."
            ),
            "source": "generated from KPP_PY/extreme_scenarios.py",
            "scenario": name,
            "time_dependence": "invariant",
            "provenance": {
                "U10_m_s": float(forcing["U10"]),
                "duration_hours": float(forcing["hours"]),
                "wind_stress_formula": "tau/rho = rho_air*cd*U10^2/rho_water, cd=1.3e-3, rho_air=1.225",
            },
        },
        "atmospheric_forcing": {
            # Kinematic surface momentum forcing tau/rho_water [m^2/s^2].
            "tau_x": float(round(tau_x, 8)),
            "tau_y": 0.0,
            # Surface heat fluxes [W/m^2]; positive into ocean.
            "q_net": float(forcing["q_net"]),
            "q_sw": float(forcing["q_sw"]),
            # Freshwater flux [m/s]; positive = freshening into ocean.
            "fw_flux": float(forcing.get("fw_flux", 0.0)),
            # Reference density for tau <-> wind-stress conversion in GGL90.
            "rho_water": float(rho_water),
        },
    }


def build_time_integration_doc(name: str, forcing: dict, dt: float,
                               output_every: int) -> dict:
    """Build the time_integration YAML document for one scenario.

    n_steps is derived from the scenario's own duration exactly as
    extreme_scenarios.run_scenario does: n_steps = round(hours*3600/dt). This
    guarantees each scenario integrates for its intended physical duration
    (e.g. arctic_convection = 72 h, hurricane_wind = 24 h) in both codebases.
    output_frequency_steps is clamped to <= n_steps so at least the final
    snapshot is always saved.
    """
    hours = float(forcing["hours"])
    n_steps = int(round(hours * 3600.0 / dt))
    if n_steps < 1:
        n_steps = 1
    out_every = int(min(output_every, n_steps))

    return {
        "metadata": {
            "name": f"scenario_{name}_time_integration",
            "description": (
                f"Time-integration controls for extreme scenario '{name}': "
                f"{forcing['label']}. Shared by KPP_PY and GGL90_PY."
            ),
            "source": "generated from KPP_PY/extreme_scenarios.py",
            "scenario": name,
            "provenance": {
                "duration_hours": hours,
                "n_steps_formula": "round(duration_hours*3600/dt_seconds)",
            },
        },
        "time_integration": {
            "dt_seconds": float(dt),
            "n_steps": n_steps,
            "output_frequency_steps": out_every,
        },
    }


def dump_yaml(doc: dict, path: Path) -> None:
    with open(path, "w") as f:
        yaml.dump(doc, f, sort_keys=False, default_flow_style=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate IC + forcing YAML pairs for every extreme scenario."
    )
    parser.add_argument("--nz", type=int, default=50,
                        help="Number of vertical levels (default: 50, matches extreme_scenarios)")
    parser.add_argument("--depth-max", type=float, default=400.0,
                        help="Domain depth [m] (default: 400, matches extreme_scenarios)")
    parser.add_argument("--coriol", type=float, default=1.0e-4,
                        help="Coriolis parameter [1/s] (default: 1.0e-4, matches extreme_scenarios)")
    parser.add_argument("--dt", type=float, default=600.0,
                        help="Timestep [s] for time_integration YAMLs (default: 600, matches extreme_scenarios)")
    parser.add_argument("--output-every", type=int, default=6,
                        help="output_frequency_steps for time_integration YAMLs "
                             "(default: 6; clamped to <= n_steps per scenario)")
    parser.add_argument("--outdir", type=str, default=str(Path(__file__).resolve().parent),
                        help="Output directory (default: this shared_yaml/ directory)")
    args = parser.parse_args()

    if args.dt <= 0.0:
        parser.error("--dt must be > 0")
    if args.output_every <= 0:
        parser.error("--output-every must be > 0")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Generating scenario YAMLs into {outdir}")
    print(f"  grid: nz={args.nz}, depth_max={args.depth_max} m, coriol={args.coriol} 1/s")
    print(f"  time: dt={args.dt} s, output_every={args.output_every} steps")
    print(f"  rho_water (shared): {KPPConstants.RHO_CONST} kg/m^3\n")

    written = []
    for name, forcing in SCENARIOS.items():
        ic_doc = build_initial_conditions_doc(name, forcing, args.nz,
                                              args.depth_max, args.coriol)
        fc_doc = build_forcing_doc(name, forcing)
        ti_doc = build_time_integration_doc(name, forcing, args.dt, args.output_every)

        ic_path = outdir / f"scenario_{name}_initial_conditions.yaml"
        fc_path = outdir / f"scenario_{name}_atmospheric_forcing.yaml"
        ti_path = outdir / f"scenario_{name}_time_integration.yaml"
        dump_yaml(ic_doc, ic_path)
        dump_yaml(fc_doc, fc_path)
        dump_yaml(ti_doc, ti_path)
        written.extend([ic_path, fc_path, ti_path])

        tau_x = fc_doc["atmospheric_forcing"]["tau_x"]
        ti = ti_doc["time_integration"]
        print(f"  {name:<26} U10={forcing['U10']:>5.1f} m/s -> tau_x={tau_x:.5f} m^2/s^2 | "
              f"Qnet={forcing['q_net']:>7.1f} Qsw={forcing['q_sw']:>6.1f} "
              f"FW={forcing.get('fw_flux', 0.0):.1e} | "
              f"{forcing['hours']:>4.0f}h -> n_steps={ti['n_steps']}")

    print(f"\nWrote {len(written)} files ({len(SCENARIOS)} scenario triples).")


if __name__ == "__main__":
    main()
