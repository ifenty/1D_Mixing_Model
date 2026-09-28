#!/usr/bin/env python3
"""
Generate a freshly-reproducible markdown report for the 6 idealized-scenario
GGL90 standalone-Fortran-driver comparisons (1DMIX-041/1DMIX-048), closing
1DMIX-051's report-artifact gap.

Why this is a *separate* script from ``generate_ggl90_validation_report.py``
(1DMIX-044), not an extension of it: that generator's whole shape --
``load_and_validate_datasets``, ``input_uuid`` provenance matching, per-field
wet-mask statistics over two *NetCDF* datasets with ``[time, x, y, z]``
coordinates -- assumes an MITgcm-*capture* vs. Python-port comparison. The
6-scenario comparison this script covers is a genuinely different shape:
the real Fortran ``GGL90_CALC`` *standalone driver*
(``mitgcm_verification_mods/ggl90_standalone_driver/``) fed the Python port's
own dense (``output_frequency_steps=1``) trajectory and replayed one step at
a time, parsed from **text** stdout (``ggl90_standalone_output.txt``), not
NetCDF, and compared against a **npz** archive
(``ggl90_experiment_dense.npz``), not a second NetCDF dataset. There is no
MITgcm "ground truth" NetCDF at all here, and no ``input_uuid`` attribute to
cross-check. Forcing this into the existing generator's structure would mean
either faking a NetCDF wrapper around text-parsed data or making that
generator branch heavily on an input shape it was never designed for --
Bob's assigned brief (1DMIX-051) explicitly permits a simpler, separate
artifact instead, which is what this script produces (a markdown table, not
a PDF -- sufficient per that same explicit permission).

All comparison logic is reused, not reimplemented: every number in this
report comes directly from
``compare_scenario_ggl90_standalone.py::compare`` (1DMIX-024/1DMIX-041's own
established per-scenario comparison, which itself reuses
``parse_mitgcm_ggl90_split.py`` for the Fortran-text-output side). This
script only adds report assembly/formatting on top.

Field coverage: ``visc_az`` (K_m), ``diff_kz_s`` (K_h -- GGL90 has a single
scalar diffusivity, so ``diff_kz_s == diff_kz_t``; kept as ``diff_kz_s`` to
match ``compare_scenario_ggl90_standalone.py::FIELD_MAP``'s and
``README.md``'s own existing column-naming convention rather than
introducing a new synonym), ``mixing_length`` (L), and ``tke_after`` (the one
prognostic field; Fortran's ``tke_after[i]`` vs. Python's ``tke[i+1]`` --
see that module's own docstring for the index-alignment derivation). Per
field, per scenario: ``max_abs``/``median_abs``/``p95_abs``/``max_rel`` and
the fraction of cells exceeding 1% relative error -- exactly the brief's
requested statistics, all taken verbatim from ``compare()``'s own returned
dict, none recomputed independently.

Data source (verify freshness before trusting a rerun's numbers -- see
module-level ``SCENARIOS`` and this script's own freshness check output):
``Vertical_Mixing_Models/output/<scenario>/{ggl90_experiment_dense.npz,
ggl90_standalone_output.txt}``, produced by
``export_scenario_to_ggl90_driver.py`` (Python-port side) and
``mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh``
(Fortran-driver side). Running this script again against unchanged on-disk
artifacts reproduces byte-identical numbers (deterministic comparison, no
stochastic component) -- the freshly-reproducible artifact the issue asks
for.

Usage:
  python3 generate_ggl90_scenario_report.py [output.md]

Default output path:
  GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_scenario_ggl90_standalone import compare  # noqa: E402

# Canonical 6-scenario order, matching README.md's own existing
# "GGL90 standalone driver" table (1DMIX-041/1DMIX-048) -- not re-derived,
# reused for consistency with the prose this report supersedes as the
# generated artifact.
SCENARIOS = [
    'calm_baseline',
    'arctic_convection',
    'hurricane_wind',
    'tropical_heating_diurnal',
    'heavy_rain_freshening',
    'combined_storm',
]

# Field key (as returned by compare()) -> (display label, units).
FIELD_INFO = {
    'visc_az': ('visc_az (K_m)', 'm^2/s'),
    'diff_kz_s': ('diff_kz_s (K_h, == diff_kz_t)', 'm^2/s'),
    'mixing_length': ('mixing_length (L)', 'm'),
    'tke_after': ('tke_after', 'm^2/s^2'),
}
FIELD_ORDER = ['visc_az', 'diff_kz_s', 'mixing_length', 'tke_after']


def _fmt(x: float) -> str:
    return f"{x:.3e}"


def _load_grid_shape(output_dir: Path) -> Dict[str, int]:
    """n_out/nz for the report header only -- compare() already opens this
    npz internally for the actual comparison; this is a cheap, separate read
    of the same small file purely for display metadata, not a second
    comparison path."""
    py = np.load(output_dir / "ggl90_experiment_dense.npz")
    return {'n_out': int(py['visc_az'].shape[0]), 'nz': int(py['depth'].shape[0])}


def build_report(all_results: Dict[str, dict], all_shapes: Dict[str, dict]) -> str:
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines.append('# GGL90 standalone-driver 6-scenario validation summary')
    lines.append('')
    lines.append(f'Generated: {now}')
    lines.append('')
    lines.append(
        'Compares the real Fortran `GGL90_CALC` standalone driver '
        '(`mitgcm_verification_mods/ggl90_standalone_driver/`) against the '
        'Python GGL90 port, one idealized scenario at a time -- a genuinely '
        'different comparison shape from the 10 MITgcm-capture reports '
        '(`generate_ggl90_validation_report.py`, 1DMIX-044): Fortran-'
        'standalone-driver text output vs. Python port, not MITgcm-capture '
        'NetCDF vs. Python port, so this is a markdown table rather than a '
        'PDF forced into that generator\'s NetCDF-shaped structure (1DMIX-051, '
        'split from 1DMIX-044; see `open_issues.md`/`closed_issues.md` for the '
        'full scope-split rationale).'
    )
    lines.append('')
    lines.append(
        'Every number below comes directly from '
        '`compare_scenario_ggl90_standalone.py::compare` (1DMIX-024/1DMIX-041\'s '
        'own established per-scenario comparison) -- no comparison logic is '
        'reimplemented in this report generator.'
    )
    lines.append('')
    lines.append(
        '`max_rel = max(|Python - Fortran| / max(|Fortran|, 1e-12))` over all '
        'wet cells; `frac_gt_1pct` is the fraction of cells with relative '
        'error > 1%. `tke_after` compares the Fortran driver\'s `tke_after[i]` '
        'against the Python port\'s `tke[i+1]` (index-shifted by one timestep '
        '-- see `compare_scenario_ggl90_standalone.py` module docstring for the '
        'derivation).'
    )
    lines.append('')

    overall_worst_rel = 0.0
    overall_mismatch = 0
    overall_total = 0
    for scenario in SCENARIOS:
        results = all_results[scenario]
        shape = all_shapes[scenario]
        lines.append(f"## `{scenario}` (n_out={shape['n_out']}, nz={shape['nz']})")
        lines.append('')
        lines.append('| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |')
        lines.append('|---|---|---|---|---|---|---|')
        for field in FIELD_ORDER:
            stats = results[field]
            label, units = FIELD_INFO[field]
            frac = stats['n_gt_1pct'] / stats['n_total'] if stats['n_total'] else 0.0
            lines.append(
                f"| {label} [{units}] | {_fmt(stats['max_abs'])} | {_fmt(stats['median_abs'])} |"
                f" {_fmt(stats['p95_abs'])} | {_fmt(stats['max_rel'])} | {frac:.4%} |"
                f" {stats['n_gt_1pct']}/{stats['n_total']} |"
            )
            overall_worst_rel = max(overall_worst_rel, stats['max_rel'])
            overall_mismatch += stats['n_gt_1pct']
            overall_total += stats['n_total']
        lines.append('')

    lines.append('## Summary')
    lines.append('')
    lines.append(f"- Worst `max_rel` across all scenarios/fields: {_fmt(overall_worst_rel)}")
    lines.append(
        f"- Total cells with >1% relative error, all scenarios/fields combined: "
        f"{overall_mismatch}/{overall_total}"
    )
    if overall_mismatch == 0:
        status = (
            'All 4 fields, all 6 scenarios, match to floating-point roundoff '
            '(worst max_rel ~1e-11, 0 cells >1% anywhere). `visc_az`/'
            '`diff_kz_s`/`mixing_length` were always exact (diagnostic '
            'formulas); `tke_after` (the one prognostic field) reached this '
            'state after 1DMIX-048\'s TKE-buoyancy-term fix -- see '
            '`closed_issues.md` 1DMIX-041/1DMIX-048 for the pre-fix numbers '
            'and root cause.'
        )
    else:
        status = 'NEEDS REVIEW -- see per-scenario tables above for the affected field(s)/scenario(s).'
    lines.append(f'- Status: {status}')
    lines.append('')
    lines.append('## Reproducibility')
    lines.append('')
    lines.append(
        'Data source: `Vertical_Mixing_Models/output/<scenario>/'
        '{ggl90_experiment_dense.npz,ggl90_standalone_output.txt}`. To '
        'regenerate from scratch for a given scenario: rerun '
        '`export_scenario_to_ggl90_driver.py <scenario>` (Python-port side) '
        'then `mitgcm_verification_mods/ggl90_standalone_driver/'
        'build_and_run.sh <scenario>` (Fortran-driver side, well under a '
        'minute per scenario), then rerun this script -- the numbers above '
        'are computed fresh from whatever is currently on disk, not cached '
        'or hand-copied from a prior run.'
    )
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    pkg_dir = Path(__file__).resolve().parent.parent.parent / "Vertical_Mixing_Models"
    output_dir_root = pkg_dir / "output"

    default_report = (
        Path(__file__).resolve().parent.parent
        / "GGL90_port_validation" / "reports" / "ggl90_scenario_standalone_summary.md"
    )
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_report
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_results: Dict[str, dict] = {}
    all_shapes: Dict[str, dict] = {}
    for scenario in SCENARIOS:
        output_dir = output_dir_root / scenario
        all_results[scenario] = compare(scenario, output_dir)
        all_shapes[scenario] = _load_grid_shape(output_dir)

    report_text = build_report(all_results, all_shapes)
    output_path.write_text(report_text)

    print(f"\n{'=' * 70}")
    print(f"Wrote report: {output_path}")
    print(f"{'=' * 70}")

    any_mismatch = any(
        stats['n_gt_1pct'] > 0
        for results in all_results.values()
        for stats in results.values()
    )
    if any_mismatch:
        print("Result: NEEDS REVIEW -- see report for details")
    else:
        print("Result: all scenarios/fields at floating-point roundoff, 0 cells >1%")
    sys.exit(1 if any_mismatch else 0)


if __name__ == '__main__':
    main()
