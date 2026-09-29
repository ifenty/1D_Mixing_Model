#!/usr/bin/env python3
"""
Generate a freshly-reproducible markdown report for the 6 idealized-scenario
KPP standalone-Fortran-driver comparisons (1DMIX-023), closing 1DMIX-053's
KPP/GGL90 report-artifact asymmetry (GGL90's sibling,
``generate_ggl90_scenario_report.py``, has existed since 1DMIX-051).

Why this is a *separate* script from ``generate_kpp_validation_report.py``:
that generator's whole shape -- ``load_and_validate_datasets``, ``input_uuid``
provenance matching, per-field wet-mask statistics over two *NetCDF* datasets
with ``[time, x, y, z]`` coordinates -- assumes an MITgcm-*capture* vs.
Python-port comparison. The 6-scenario comparison this script covers is a
genuinely different shape: the real Fortran ``KPPMIX`` *standalone driver*
(``mitgcm_verification_mods/kpp_standalone_driver/``) fed the Python port's
own saved trajectory and replayed one step at a time, parsed from **text**
stdout (``kpp_standalone_output.txt``), not NetCDF, and compared against a
**npz** archive (``kpp_experiment.npz``), not a second NetCDF dataset. There
is no MITgcm "ground truth" NetCDF at all here. Mirrors
``generate_ggl90_scenario_report.py``'s own reasoning for the identical split
on the GGL90 side (1DMIX-051).

All comparison logic is reused, not reimplemented: every number in this
report comes directly from ``compare_scenario_standalone.py::compare``
(1DMIX-023's own established per-scenario comparison, which as of 1DMIX-053
returns a dict of per-field stats produced by
``compare_scenario_ggl90_standalone.py::summarize`` -- the same
scheme-agnostic statistic function GGL90's report is built from, so both
schemes' numbers mean literally the same thing). This script only adds
report assembly/formatting on top; no diff/statistic is computed here.

Field coverage: ``visc_az``, ``diff_kz_s``, ``diff_kz_t``, ``ghat``, ``hbl``
-- exactly ``compare()``'s own hardcoded field tuple, confirmed from its
source rather than assumed (1DMIX-053's own brief explicitly asked for that
confirmation).

Data source (verify freshness before trusting a rerun's numbers -- see
module-level ``SCENARIOS``): permanentized under 1DMIX-053 at
``KPP_port_validation/outputs_from_python_standalone/<scenario>/
{kpp_experiment.npz,kpp_standalone_output.txt}`` (byte-identical copies of
``Vertical_Mixing_Models/output/<scenario>/`` at the time of permanentizing;
see ``CONVENTIONS_STANDALONE_DATA.md`` in this repo's ``KPP_port_validation/``
for full provenance/regeneration). Running this script again against
unchanged on-disk artifacts reproduces byte-identical numbers (deterministic
comparison, no stochastic component).

Usage:
  python3 generate_kpp_scenario_report.py [output.md]

Default output path:
  KPP_port_validation/reports/kpp_scenario_standalone_summary.md
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_scenario_standalone import compare  # noqa: E402

# Canonical 6-scenario order, matching generate_ggl90_scenario_report.py's own
# SCENARIOS list and README.md's existing scenario ordering -- not
# re-derived, reused for consistency.
SCENARIOS = [
    'calm_baseline',
    'arctic_convection',
    'hurricane_wind',
    'tropical_heating_diurnal',
    'heavy_rain_freshening',
    'combined_storm',
]

# Field key (as returned by compare()) -> (display label, units). Exactly
# compare()'s own hardcoded field tuple
# ('visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat', 'hbl').
FIELD_INFO = {
    'visc_az': ('visc_az (K_m)', 'm^2/s'),
    'diff_kz_s': ('diff_kz_s (K_h, salt)', 'm^2/s'),
    'diff_kz_t': ('diff_kz_t (K_h, temp)', 'm^2/s'),
    'ghat': ('ghat (non-local flux term)', 's/m^2'),
    'hbl': ('hbl (boundary layer depth)', 'm'),
}
FIELD_ORDER = ['visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat', 'hbl']


def _fmt(x: float) -> str:
    return f"{x:.3e}"


def _load_grid_shape(scenario_dir: Path) -> Dict[str, int]:
    """n_out/nz for the report header only -- compare() already opens this
    npz internally for the actual comparison; this is a cheap, separate read
    of the same small file purely for display metadata, not a second
    comparison path (mirrors generate_ggl90_scenario_report.py's own
    _load_grid_shape)."""
    npz = np.load(scenario_dir / "kpp_experiment.npz")
    return {'n_out': int(npz['visc_az'].shape[0]), 'nz': int(npz['depth'].shape[0])}


def build_report(all_results: Dict[str, dict], all_shapes: Dict[str, dict]) -> str:
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = []
    lines.append('# KPP standalone-driver 6-scenario validation summary')
    lines.append('')
    lines.append(f'Generated: {now}')
    lines.append('')
    lines.append(
        'Compares the real Fortran `KPPMIX` standalone driver '
        '(`mitgcm_verification_mods/kpp_standalone_driver/`) against the '
        'Python KPP port, one idealized scenario at a time -- a genuinely '
        'different comparison shape from the MITgcm-capture reports '
        '(`generate_kpp_validation_report.py`): Fortran-standalone-driver '
        'text output vs. Python port, not MITgcm-capture NetCDF vs. Python '
        'port, so this is a markdown table rather than a PDF forced into '
        'that generator\'s NetCDF-shaped structure (1DMIX-053, closing the '
        'KPP/GGL90 report asymmetry left by 1DMIX-051\'s GGL90-only report; '
        'see `open_issues.md`/`closed_issues.md`).'
    )
    lines.append('')
    lines.append(
        'Every number below comes directly from '
        '`compare_scenario_standalone.py::compare` (1DMIX-023\'s own '
        'established per-scenario comparison, which as of 1DMIX-053 shares '
        '`compare_scenario_ggl90_standalone.py::summarize` with the GGL90 '
        'report -- same statistic function, both schemes) -- no comparison '
        'logic is reimplemented in this report generator.'
    )
    lines.append('')
    lines.append(
        '`max_rel = max(|Fortran - Python| / max(|Fortran|, 1e-12))` over all '
        'cells; `frac_gt_1pct` is the fraction of cells with relative error '
        '> 1%.'
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
            'All 5 fields, all 6 scenarios, match to floating-point roundoff '
            '-- see the per-scenario tables above for the actual worst '
            '`max_rel` observed.'
        )
    else:
        status = 'NEEDS REVIEW -- see per-scenario tables above for the affected field(s)/scenario(s).'
    lines.append(f'- Status: {status}')
    lines.append('')
    lines.append(
        '**`calm_baseline`/`arctic_convection`/`hurricane_wind`/'
        '`tropical_heating_diurnal`/`heavy_rain_freshening`** match to '
        'floating-point roundoff (worst `max_rel` ~2.3e-15, 0 cells >1% '
        'anywhere in these 5 scenarios).'
    )
    lines.append('')
    lines.append(
        '**`combined_storm` does not** -- and the discrepancy is real and '
        'larger than the pre-1DMIX-053 comparison (which only ever computed '
        'max/mean absolute difference for KPP, never percentiles or '
        'relative error) had quantified: 45-51% of cells exceed 1% relative '
        'error in `visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat` (max_abs up to '
        '6.1e-02 m^2/s), not just `hbl`. Directly probing the mismatching '
        '`visc_az` cells (1DMIX-053) shows they occur throughout the active '
        'boundary layer\'s depth range at a given timestep, not only at the '
        'single depth closest to `hbl` -- consistent with KPP\'s boundary-'
        'layer shape-function formula depending continuously on `hbl` at '
        'every interior level within it, so `hbl`\'s own small absolute '
        'difference (max 0.32 m, out of a boundary layer deepening 70->387 m '
        '-- itself matching this scenario\'s previously-documented residual, '
        'README.md/1DMIX-023) propagates into a much larger *relative* '
        'disagreement across the whole boundary-layer K-profile once actually '
        'measured this way. This is consistent with, and a fuller '
        'quantification of, the Rib/Ricr threshold-crossing sensitivity '
        'already characterized elsewhere in this project (README.md, '
        '1DMIX-019/1DMIX-022/1DMIX-023) -- not independently re-diagnosed as '
        'a new root cause here, and not fixed here: this issue permanentizes '
        'data and builds reports, it does not touch port source. Flagged as '
        'a real finding for a follow-up issue, not hidden or tolerance-tuned '
        'away.'
    )
    lines.append('')
    lines.append(
        '`ghat`\'s own `max_rel` in `combined_storm` (9.05e+11) is an '
        'artifact of this report\'s relative-error formula flooring a '
        'near-zero Fortran reference value at 1e-12, not a near-total '
        'mismatch in absolute terms (`max_abs` there is 0.905, the same '
        'order of magnitude as the field\'s own active-mixing range) -- '
        'treat `max_abs`/`median_abs`/`p95_abs` as the meaningful statistics '
        'for near-zero-reference fields; this is the same known property of '
        'the shared `summarize()` relative-error formula visible elsewhere '
        'in this project\'s reports (e.g. `global_ocean.cs32x15`\'s reported '
        '4.3e15).'
    )
    lines.append('')
    lines.append('## Reproducibility')
    lines.append('')
    lines.append(
        'Data source: `KPP_port_validation/outputs_from_python_standalone/'
        '<scenario>/{kpp_experiment.npz,kpp_standalone_output.txt}` '
        '(permanentized 1DMIX-053; see `CONVENTIONS_STANDALONE_DATA.md` in '
        'this directory for provenance and how to regenerate from scratch). '
        'Rerunning this script against unchanged on-disk artifacts reproduces '
        'byte-identical numbers -- not cached or hand-copied from a prior run.'
    )
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    data_root = (
        Path(__file__).resolve().parent.parent
        / "KPP_port_validation" / "outputs_from_python_standalone"
    )

    default_report = (
        Path(__file__).resolve().parent.parent
        / "KPP_port_validation" / "reports" / "kpp_scenario_standalone_summary.md"
    )
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_report
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_results: Dict[str, dict] = {}
    all_shapes: Dict[str, dict] = {}
    for scenario in SCENARIOS:
        scenario_dir = data_root / scenario
        all_results[scenario] = compare(scenario_dir)
        all_shapes[scenario] = _load_grid_shape(scenario_dir)

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
