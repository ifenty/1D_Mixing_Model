"""
Validate shared YAML files used by KPP and GGL90.

Checks performed:
1. Shared initial conditions schema and profile lengths vs drF.
2. Shared forcing schema and numeric sanity.
3. Shared runtime controls schema and positivity.
4. KPP output field list validity.
5. GGL90 output field list validity.

Usage:
  python3 validate_shared_yaml.py
  python3 validate_shared_yaml.py --initial-condition-yaml path/to/ic.yaml ...
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import yaml


KPP_ALLOWED_OUTPUT_FIELDS = {
    "time_seconds",
    "hbl",
    "ustar",
    "bfsfc",
    "theta",
    "salt",
    "u_vel",
    "v_vel",
    "visc_az",
    "diff_kz_s",
    "diff_kz_t",
    "ghat",
    "max_visc_az",
    "max_diff_kz_s",
    "max_diff_kz_t",
}

GGL90_ALLOWED_OUTPUT_FIELDS = {
    "time_days",
    "temp",
    "tke",
    "kappa_m",
    "mld",
    "sst",
    "max_tke",
}


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return data


def require_numeric_list(name: str, values: Any, expected_len: int | None = None) -> List[float]:
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError(f"{name} must be a non-empty list")
    out = []
    for i, v in enumerate(values):
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            raise ValueError(f"{name}[{i}] must be numeric")
    if expected_len is not None and len(out) != expected_len:
        raise ValueError(f"{name} must have length {expected_len}, got {len(out)}")
    return out


def validate_initial_conditions(path: Path) -> None:
    data = load_yaml(path)
    if "initial_conditions" not in data:
        raise ValueError(f"{path}: missing 'initial_conditions'")

    ic = data["initial_conditions"]
    if not isinstance(ic, dict):
        raise ValueError(f"{path}: 'initial_conditions' must be a mapping")

    drf = require_numeric_list("initial_conditions.drF", ic.get("drF"))
    if any(d <= 0.0 for d in drf):
        raise ValueError("initial_conditions.drF values must all be > 0")

    nz = len(drf)
    require_numeric_list("initial_conditions.theta", ic.get("theta"), expected_len=nz)
    require_numeric_list("initial_conditions.salt", ic.get("salt"), expected_len=nz)
    require_numeric_list("initial_conditions.u_vel", ic.get("u_vel"), expected_len=nz)
    require_numeric_list("initial_conditions.v_vel", ic.get("v_vel"), expected_len=nz)

    if "coriol" in ic:
        _ = float(ic["coriol"])

    total_depth = sum(drf)
    print(f"OK  initial_conditions: nz={nz}, sum(drF)={total_depth:.3f} m")


def validate_forcing(path: Path) -> None:
    data = load_yaml(path)
    if "atmospheric_forcing" not in data:
        raise ValueError(f"{path}: missing 'atmospheric_forcing'")

    atm = data["atmospheric_forcing"]
    if not isinstance(atm, dict):
        raise ValueError(f"{path}: 'atmospheric_forcing' must be a mapping")

    # Required by shared setup workflow (can still be constant in time).
    for key in ("tau_x", "tau_y", "q_net", "q_sw", "fw_flux"):
        if key not in atm:
            raise ValueError(f"{path}: missing atmospheric_forcing.{key}")
        _ = float(atm[key])

    if "rho_water" in atm and float(atm["rho_water"]) <= 0.0:
        raise ValueError(f"{path}: atmospheric_forcing.rho_water must be > 0")

    print("OK  atmospheric_forcing: required scalar keys present")


def validate_runtime(path: Path) -> Dict[str, float | int]:
    data = load_yaml(path)
    if "time_integration" not in data:
        raise ValueError(f"{path}: missing 'time_integration'")

    tcfg = data["time_integration"]
    if not isinstance(tcfg, dict):
        raise ValueError(f"{path}: 'time_integration' must be a mapping")

    for key in ("dt_seconds", "n_steps", "output_frequency_steps"):
        if key not in tcfg:
            raise ValueError(f"{path}: missing time_integration.{key}")

    dt = float(tcfg["dt_seconds"])
    n_steps = int(tcfg["n_steps"])
    output_every = int(tcfg["output_frequency_steps"])

    if dt <= 0.0:
        raise ValueError("time_integration.dt_seconds must be > 0")
    if n_steps <= 0:
        raise ValueError("time_integration.n_steps must be > 0")
    if output_every <= 0:
        raise ValueError("time_integration.output_frequency_steps must be > 0")
    if output_every > n_steps:
        print("WARN runtime: output_frequency_steps > n_steps (only first snapshot likely saved)")

    print(f"OK  runtime: dt={dt:.3f}s, n_steps={n_steps}, output_every={output_every}")
    return {
        "dt_seconds": dt,
        "n_steps": n_steps,
        "output_frequency_steps": output_every,
    }


def validate_output_fields(path: Path, allowed: set[str], label: str) -> None:
    data = load_yaml(path)
    if "output_fields" not in data:
        raise ValueError(f"{path}: missing 'output_fields'")

    fields = data["output_fields"]
    if not isinstance(fields, list) or len(fields) == 0:
        raise ValueError(f"{path}: output_fields must be a non-empty list")

    seen = set()
    for idx, field in enumerate(fields):
        if not isinstance(field, str):
            raise ValueError(f"{path}: output_fields[{idx}] must be a string")
        if field in seen:
            print(f"WARN {label}: duplicate output field '{field}'")
        seen.add(field)
        if field not in allowed:
            allowed_sorted = ", ".join(sorted(allowed))
            raise ValueError(
                f"{path}: invalid {label} output field '{field}'. Allowed: {allowed_sorted}"
            )

    print(f"OK  {label} output_fields: {len(fields)} fields")


def validate_physical_parameters(path: Path) -> Dict[str, float]:
    data = load_yaml(path)
    if "physical_parameters" not in data:
        raise ValueError(f"{path}: missing 'physical_parameters'")

    pp = data["physical_parameters"]
    if not isinstance(pp, dict):
        raise ValueError(f"{path}: 'physical_parameters' must be a mapping")

    for key in ("gravity", "rho_const", "heat_capacity_cp"):
        if key not in pp:
            raise ValueError(f"{path}: missing physical_parameters.{key}")

    gravity = float(pp["gravity"])
    rho_const = float(pp["rho_const"])
    heat_capacity_cp = float(pp["heat_capacity_cp"])
    if gravity <= 0.0 or rho_const <= 0.0 or heat_capacity_cp <= 0.0:
        raise ValueError("physical_parameters values must be > 0")

    print(
        "OK  physical_parameters: "
        f"g={gravity}, rho_const={rho_const}, cp={heat_capacity_cp}"
    )
    return {
        "gravity": gravity,
        "rho_const": rho_const,
        "heat_capacity_cp": heat_capacity_cp,
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    default_ic = here / "shared_initial_conditions.yaml"
    default_forcing = here / "shared_atmospheric_forcing.yaml"
    default_runtime = here / "shared_time_integration.yaml"
    default_physical = here / "physical_parameters.yaml"
    default_kpp_fields = here.parent / "KPP" / "kpp_output_fields.yaml"
    default_ggl_fields = here.parent.parent / "GGL90" / "ggl90_output_fields.yaml"

    parser = argparse.ArgumentParser(description="Validate shared YAML files for KPP and GGL90")
    parser.add_argument("--initial-condition-yaml", type=str, default=str(default_ic))
    parser.add_argument("--forcing-yaml", type=str, default=str(default_forcing))
    parser.add_argument("--runtime-yaml", type=str, default=str(default_runtime))
    parser.add_argument("--physical-parameters-yaml", type=str, default=str(default_physical))
    parser.add_argument("--kpp-output-fields-yaml", type=str, default=str(default_kpp_fields))
    parser.add_argument("--ggl90-output-fields-yaml", type=str, default=str(default_ggl_fields))
    args = parser.parse_args()

    try:
        validate_initial_conditions(Path(args.initial_condition_yaml))
        validate_forcing(Path(args.forcing_yaml))
        _ = validate_runtime(Path(args.runtime_yaml))
        _ = validate_physical_parameters(Path(args.physical_parameters_yaml))
        validate_output_fields(Path(args.kpp_output_fields_yaml), KPP_ALLOWED_OUTPUT_FIELDS, "KPP")
        validate_output_fields(Path(args.ggl90_output_fields_yaml), GGL90_ALLOWED_OUTPUT_FIELDS, "GGL90")
    except Exception as exc:
        print(f"FAIL {exc}")
        return 1

    print("PASS all YAML validation checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
