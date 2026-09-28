#!/usr/bin/env python3
"""
Generate comprehensive GGL90 validation report comparing MITgcm and Python
outputs. GGL90 counterpart of ``generate_kpp_validation_report.py`` (1DMIX-044
-- that script had no GGL90 equivalent, and every KPP-side statistic/plot
convention it established had to be re-derived for GGL90's own field set
rather than assumed to transfer unchanged).

Mirrors that script's overall shape (provenance tracking via the shared
``input_uuid`` attribute, statistics tables, profile/scatter plots, a single
multi-page PDF report) but compares GGL90's own single-step-replay fields --
``visc_az``/``diff_kz``/``mixing_length``/``tke_after`` (all volumetric,
``[time, x, y, z]``) -- not KPP's ``hbl`` (scalar boundary-layer depth) plus
``visc_az``/``diff_kz_s``/``diff_kz_t``/``ghat`` split across ``z``/``z_iface``.
Two structural differences from the KPP generator follow directly from that:

- GGL90 has no scalar diagnostic analogous to ``hbl``, so there is no
  dedicated "boundary layer depth" page; every field gets the same
  statistics + scatter/histogram treatment, with an additional vertical-
  profile page when the capture is a single column.
- ``run_ggl90_from_netcdf_input.py::run`` fills a partially-wet column's
  excluded region (below the real seafloor, or above a real ice-shelf draft
  for an ``ALLOW_SHELFICE`` experiment, e.g. isomip) with NaN rather than
  guessing MITgcm's own non-trivial fill there (see that function's own
  "truncation note" docstring) -- this generator reuses
  ``compare_ggl90.py::summarize``'s exact wet-mask convention (mask on the
  Python field's NaN, not MITgcm's) rather than reinventing it, so those
  genuinely-not-compared cells are excluded from every statistic here too.

Field names/units/comparison convention (NaN-exclusion, ``rel = diff /
max(|mitgcm|, 1e-12)``) are taken directly from ``compare_ggl90.py`` -- the
existing lightweight, console-only comparison script already established for
this project -- not reinvented independently.

Usage:
  python generate_ggl90_validation_report.py <mitgcm_output.nc> <python_output.nc> [report.pdf]

Example:
  python generate_ggl90_validation_report.py \\
    GGL90_port_validation/outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20_1dmix024.nc \\
    GGL90_port_validation/outputs_from_python/python_ggl90_outputs_vermix_20_1dmix024.nc \\
    GGL90_port_validation/reports/ggl90_validation_vermix.pdf
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# Field name, human label, units and plot-scale convention. Names match
# compare_ggl90.py::FIELD_MAP exactly (GGL90's mitgcm/python output field
# names are identical, unlike KPP's diff_kz_s/diff_kz_t split) -- reusing
# that established mapping rather than re-deriving it.
FIELD_INFO = {
    'visc_az': {
        'label': 'Vertical eddy viscosity (K_m)',
        'units': 'm^2/s',
        'log_scale': True,
    },
    'diff_kz': {
        'label': 'Vertical eddy diffusivity (K_h)',
        'units': 'm^2/s',
        'log_scale': True,
    },
    'mixing_length': {
        'label': 'GGL90 mixing length (L)',
        'units': 'm',
        'log_scale': False,
    },
    'tke_after': {
        'label': 'TKE at t+1 (single-step replay)',
        'units': 'm^2/s^2',
        'log_scale': False,
    },
}
FIELD_ORDER = ['visc_az', 'diff_kz', 'mixing_length', 'tke_after']

# Cap the number of points actually drawn in a scatter plot. Statistics are
# always computed over the full wet population; only the scatter plot's
# rendering is subsampled, since isomip/global_ocean_90x40x15/
# global_ocean_cs32x15 have wet-cell counts (1.4M/486K/814K respectively)
# large enough that an unsampled matplotlib scatter would be slow to render
# and bloat the PDF without adding visual information over a subsample.
_MAX_SCATTER_POINTS = 20000
_SCATTER_SEED = 0


def load_and_validate_datasets(file1: Path, file2: Path) -> Tuple[xr.Dataset, xr.Dataset, Dict]:
    """
    Load MITgcm and Python GGL90 output datasets and perform provenance checks.

    Mirrors generate_kpp_validation_report.py::load_and_validate_datasets.

    Returns
    -------
    ds1, ds2 : xr.Dataset
        MITgcm and Python datasets, respectively.
    metadata : dict
        Provenance and metadata information.
    """
    print(f"Loading MITgcm outputs: {file1.name}")
    ds1 = xr.open_dataset(file1)

    print(f"Loading Python outputs:  {file2.name}")
    ds2 = xr.open_dataset(file2)

    metadata = {
        'file1': str(file1),
        'file2': str(file2),
        'label1': 'MITgcm',
        'label2': 'Python',
    }

    # Provenance check. GGL90 outputs use the same input_uuid attribute
    # convention as KPP's (both are set from inputs_ds.attrs['uuid'], see
    # run_ggl90_from_netcdf_input.py::run and
    # run_kpp_from_netcdf_input.py::run_python_kpp_on_dataset).
    uuid1 = ds1.attrs.get('input_uuid', 'N/A')
    uuid2 = ds2.attrs.get('input_uuid', 'N/A')
    metadata['uuid1'] = uuid1
    metadata['uuid2'] = uuid2
    metadata['uuid_match'] = (uuid1 == uuid2) and (uuid1 != 'N/A')

    print("\nProvenance Check:")
    print(f"  MITgcm input_uuid: {uuid1}")
    print(f"  Python input_uuid: {uuid2}")
    if metadata['uuid_match']:
        print("  ✅ UUIDs match - same inputs used")
    else:
        print("  ⚠️  UUID mismatch - different inputs!")

    print("\nDimensions:")
    print(f"  MITgcm: time={len(ds1.time)}, x={len(ds1.x)}, y={len(ds1.y)}, z={len(ds1.z)}")
    print(f"  Python: time={len(ds2.time)}, x={len(ds2.x)}, y={len(ds2.y)}, z={len(ds2.z)}")

    # Compare only the dims GGL90's own 4 compared fields actually use
    # (time/x/y/z). Unlike generate_kpp_validation_report.py's identical-
    # looking `ds1.sizes != ds2.sizes` check, comparing the *full* sizes
    # dict here is a false positive: MITgcm's GGL90 output NetCDF always
    # carries an unused `z_iface` dimension (inherited from the shared
    # parser also used for KPP's z_iface-located fields), which the Python
    # GGL90 output never writes since none of visc_az/diff_kz/
    # mixing_length/tke_after are z_iface-located -- confirmed by direct
    # inspection, not a real MITgcm-vs-Python discrepancy.
    common_dims = ('time', 'x', 'y', 'z')
    if any(ds1.sizes.get(d) != ds2.sizes.get(d) for d in common_dims):
        print("  ⚠️  WARNING: Dimension mismatch!")

    return ds1, ds2, metadata


def compute_field_statistics(ds1: xr.Dataset, ds2: xr.Dataset, field: str) -> Optional[Dict]:
    """
    Compute median/p95/max absolute and relative-error statistics for one
    GGL90 field, using compare_ggl90.py::summarize's exact wet-mask and
    relative-error convention (NaN-exclusion on the Python field, ``rel =
    diff / max(|mitgcm|, 1e-12)``) rather than KPP's "active mixing,
    mitgcm > 1e-6" threshold -- GGL90's background viscosity/diffusivity
    floor means every wet cell is a meaningful comparison, not just cells
    above an activity threshold.

    Returns
    -------
    dict or None
        None only if every cell is NaN-excluded (would be an empty
        comparison -- not expected for any of this project's real captures,
        but guarded explicitly rather than silently producing statistics
        over zero samples, per this project's own evidence-recovery
        convention: "An empty ... scientific comparison cannot pass.").
    """
    mitgcm = ds1[field].values
    python = ds2[field].values

    wet = ~np.isnan(python)
    n_total = python.size
    n_excluded = int(n_total - wet.sum())
    a = mitgcm[wet]
    b = python[wet]

    if a.size == 0:
        print(f"  ⚠️  {field}: zero wet cells to compare -- skipping")
        return None

    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)

    stats = {
        'field': field,
        'n_points': int(a.size),
        'n_excluded': n_excluded,
        'median_abs': float(np.median(diff)),
        'p95_abs': float(np.percentile(diff, 95)),
        'max_abs': float(np.max(diff)),
        'median_rel': float(np.median(rel)),
        'p95_rel': float(np.percentile(rel, 95)),
        'max_rel': float(np.max(rel)),
        'frac_gt_1pct': float(np.mean(rel > 0.01)),
    }

    excluded_note = f" (excluded {n_excluded} below-seafloor/above-ice-shelf NaN cells)" if n_excluded else ""
    print(f"\n{field} ({FIELD_INFO[field]['label']}, {FIELD_INFO[field]['units']}){excluded_note}:")
    print(f"  Median |diff|: {stats['median_abs']:.6e}   P95 |diff|: {stats['p95_abs']:.6e}   Max |diff|: {stats['max_abs']:.6e}")
    print(f"  Median rel:    {stats['median_rel']:.6e}   P95 rel:    {stats['p95_rel']:.6e}   Max rel:    {stats['max_rel']:.6e}")
    print(f"  Fraction >1% rel: {stats['frac_gt_1pct']:.4%}   Points compared: {stats['n_points']}")

    if stats['median_rel'] < 0.001:
        print("  ✅ EXCELLENT - median rel error < 0.1%")
    elif stats['median_rel'] < 0.01:
        print("  ✅ GOOD - median rel error < 1%")
    else:
        print("  ⚠️  CHECK - median rel error >= 1%")

    return stats


def _subsample_for_scatter(a: np.ndarray, b: np.ndarray, seed: int = _SCATTER_SEED) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """Random subsample of (a, b) for scatter-plot rendering only.

    Returns (a_sub, b_sub, n_drawn, n_total). Statistics elsewhere in this
    report always use the full, unsampled population -- only this plot's
    point count is capped, purely for rendering/PDF-size reasons (see
    module docstring).
    """
    n_total = a.size
    if n_total <= _MAX_SCATTER_POINTS:
        return a, b, n_total, n_total
    rng = np.random.default_rng(seed)
    idx = rng.choice(n_total, size=_MAX_SCATTER_POINTS, replace=False)
    return a[idx], b[idx], _MAX_SCATTER_POINTS, n_total


def _add_title_page(pdf: PdfPages, ds1: xr.Dataset, ds2: xr.Dataset, metadata: Dict) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.75, 'GGL90 Validation Report', ha='center', va='center',
              fontsize=28, weight='bold')
    fig.text(0.5, 0.68, 'MITgcm vs Python Port Comparison (single-step replay)',
              ha='center', va='center', fontsize=16)

    info_text = [
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "MITgcm Reference:",
        f"  File: {Path(metadata['file1']).name}",
        f"  UUID: {metadata['uuid1']}",
        "",
        "Python Port Output:",
        f"  File: {Path(metadata['file2']).name}",
        f"  UUID: {metadata['uuid2']}",
        "",
        f"Provenance: {'✅ UUIDs match' if metadata['uuid_match'] else '⚠️ UUID mismatch'}",
        "",
        f"Timesteps: {len(ds1.time)}",
        f"Grid: {len(ds1.x)} × {len(ds1.y)} × {len(ds1.z)}",
        "",
        "Fields compared: visc_az, diff_kz, mixing_length, tke_after",
        "(GGL90 single-step replay: Python fed MITgcm's own captured",
        " tke_before(t); only the one-step update is compared, isolating",
        " agreement on the physics formula from trajectory drift.)",
    ]
    fig.text(0.5, 0.55, '\n'.join(info_text), ha='center', va='top',
              fontsize=11, family='monospace')
    plt.axis('off')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _add_statistics_page(pdf: PdfPages, all_stats: Dict[str, Optional[Dict]]) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.95, 'GGL90 Field Statistics', ha='center', va='top',
              fontsize=18, weight='bold')

    lines = ["Wet-cell comparison (NaN-excluded below-seafloor/above-ice-shelf cells)",
             "=" * 78, ""]
    for field in FIELD_ORDER:
        stats = all_stats.get(field)
        info = FIELD_INFO[field]
        lines.append(f"{field}  ({info['label']}, {info['units']})")
        if stats is None:
            lines.extend(["  No wet cells to compare.", ""])
            continue
        status = ("✅ EXCELLENT" if stats['median_rel'] < 0.001 else
                   "✅ GOOD" if stats['median_rel'] < 0.01 else
                   "⚠️ CHECK")
        lines.extend([
            f"  Status: {status}",
            f"  Median |diff|: {stats['median_abs']:.4e}    P95 |diff|: {stats['p95_abs']:.4e}    Max |diff|: {stats['max_abs']:.4e}",
            f"  Median rel:    {stats['median_rel']:.4e}    P95 rel:    {stats['p95_rel']:.4e}    Max rel:    {stats['max_rel']:.4e}",
            f"  Fraction >1% rel error: {stats['frac_gt_1pct']:.4%}",
            f"  Points compared: {stats['n_points']}" + (
                f"  (excluded {stats['n_excluded']} NaN cells)" if stats['n_excluded'] else ""),
            "",
        ])

    fig.text(0.5, 0.87, '\n'.join(lines), ha='center', va='top', fontsize=8.5,
              family='monospace')
    plt.axis('off')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _add_field_scatter_page(pdf: PdfPages, ds1: xr.Dataset, ds2: xr.Dataset,
                             field: str, stats: Dict) -> None:
    """2x2 scatter/histogram page for one field -- generated for every
    field regardless of grid shape (mirrors
    generate_kpp_validation_report.py's HBL page, generalized here since
    GGL90 has no scalar diagnostic to give that treatment to exclusively).
    """
    info = FIELD_INFO[field]
    mitgcm = ds1[field].values
    python = ds2[field].values
    wet = ~np.isnan(python)
    a_full = mitgcm[wet]
    b_full = python[wet]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(f"{field} ({info['label']}) -- MITgcm vs Python", fontsize=14, weight='bold')

    # MITgcm distribution histogram (full population -- cheap regardless of size).
    ax = axes[0, 0]
    ax.hist(a_full, bins=40, edgecolor='black', alpha=0.7)
    ax.set_xlabel(f"MITgcm {field} ({info['units']})", fontsize=10)
    ax.set_ylabel('Frequency', fontsize=10)
    ax.set_title('MITgcm Distribution', fontsize=11, weight='bold')
    if info['log_scale']:
        ax.set_xscale('symlog')
    ax.grid(True, alpha=0.3)

    # Scatter (subsampled for rendering only -- see _subsample_for_scatter).
    a_plot, b_plot, n_drawn, n_total = _subsample_for_scatter(a_full, b_full)
    ax = axes[0, 1]
    ax.scatter(a_plot, b_plot, alpha=0.4, s=10, c='blue', edgecolors='none')
    lim_min = float(min(a_plot.min(), b_plot.min()))
    lim_max = float(max(a_plot.max(), b_plot.max()))
    if lim_min < lim_max:
        ax.plot([lim_min, lim_max], [lim_min, lim_max], 'r--', linewidth=2, label='1:1 line')
    ax.set_xlabel(f"MITgcm {field} ({info['units']})", fontsize=10)
    ax.set_ylabel(f"Python {field} ({info['units']})", fontsize=10)
    title = 'Scatter Plot' if n_drawn == n_total else f'Scatter Plot ({n_drawn} of {n_total} pts)'
    ax.set_title(title, fontsize=11, weight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Difference histogram (full population).
    ax = axes[1, 0]
    diff = b_full - a_full
    ax.hist(diff, bins=40, edgecolor='black', alpha=0.7)
    ax.axvline(0, color='r', linestyle='--', linewidth=2, label='Zero')
    ax.axvline(float(np.mean(diff)), color='green', linestyle='--', linewidth=2,
               label=f'Mean={np.mean(diff):.3e}')
    ax.set_xlabel(f"Difference: Python - MITgcm ({info['units']})", fontsize=10)
    ax.set_ylabel('Frequency', fontsize=10)
    ax.set_title('Difference Distribution', fontsize=11, weight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Statistics text.
    ax = axes[1, 1]
    ax.axis('off')
    status = ("✅ EXCELLENT" if stats['median_rel'] < 0.001 else
               "✅ GOOD" if stats['median_rel'] < 0.01 else
               "⚠️ CHECK")
    stats_text = [
        f"{field} Statistics:",
        '─' * 35,
        f"Median |diff|: {stats['median_abs']:.4e}",
        f"P95 |diff|:    {stats['p95_abs']:.4e}",
        f"Max |diff|:    {stats['max_abs']:.4e}",
        "",
        f"Median rel:    {stats['median_rel']:.4e}",
        f"P95 rel:       {stats['p95_rel']:.4e}",
        f"Max rel:       {stats['max_rel']:.4e}",
        "",
        f"Fraction >1% rel: {stats['frac_gt_1pct']:.4%}",
        f"Points compared:  {stats['n_points']}",
    ]
    if stats['n_excluded']:
        stats_text.append(f"NaN-excluded:     {stats['n_excluded']}")
    stats_text.extend(['', '─' * 35, 'Assessment:', status])
    ax.text(0.1, 0.95, '\n'.join(stats_text), transform=ax.transAxes, fontsize=9,
            verticalalignment='top', family='monospace')

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _add_field_profile_page(pdf: PdfPages, ds1: xr.Dataset, ds2: xr.Dataset, field: str) -> None:
    """Vertical-profile comparison page for a single-column capture
    (nx=ny=1), mirroring generate_kpp_validation_report.py's per-field
    profile pages. Skipped entirely for multi-column captures (isomip,
    global_ocean_90x40x15, global_ocean_cs32x15) -- a single 1-D depth
    profile is not a meaningful summary of a multi-tile domain; those rely
    on the scatter/histogram page instead, same as KPP's own convention for
    lab_sea.
    """
    info = FIELD_INFO[field]
    depth = ds1['depth'].values

    fig, axes = plt.subplots(1, 3, figsize=(11, 8.5), sharey=True)
    fig.suptitle(f"{field} Vertical Profiles ({info['label']})", fontsize=14, weight='bold')

    n_time = len(ds1.time)
    time_indices = np.linspace(0, n_time - 1, min(5, n_time), dtype=int)
    colors = plt.cm.viridis(np.linspace(0, 1, len(time_indices)))

    for idx, t_idx in enumerate(time_indices):
        v1 = ds1[field].isel(time=t_idx, x=0, y=0).values
        v2 = ds2[field].isel(time=t_idx, x=0, y=0).values
        label = f't={t_idx}' if len(time_indices) <= 5 else None
        axes[0].plot(v1, depth, linewidth=2, color=colors[idx], label=label)
        axes[1].plot(v2, depth, linewidth=2, color=colors[idx])
        axes[2].plot(v2 - v1, depth, linewidth=2, color=colors[idx])

    axes[0].set_title('MITgcm', fontsize=11, weight='bold')
    axes[0].set_xlabel(f"{field} ({info['units']})", fontsize=10)
    axes[0].set_ylabel('Depth (m)', fontsize=10)
    if info['log_scale']:
        axes[0].set_xscale('symlog')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(fontsize=8)

    axes[1].set_title('Python', fontsize=11, weight='bold')
    axes[1].set_xlabel(f"{field} ({info['units']})", fontsize=10)
    if info['log_scale']:
        axes[1].set_xscale('symlog')
    axes[1].grid(True, alpha=0.3)

    axes[2].set_title('Difference (Python - MITgcm)', fontsize=11, weight='bold')
    axes[2].set_xlabel(f"Δ{field} ({info['units']})", fontsize=10)
    axes[2].axvline(0, color='r', linestyle='--', linewidth=2, alpha=0.7)
    axes[2].ticklabel_format(style='scientific', axis='x', scilimits=(0, 0))
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _add_summary_page(pdf: PdfPages, metadata: Dict, all_stats: Dict[str, Optional[Dict]]) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.95, 'Validation Summary & Assessment', ha='center', va='top',
              fontsize=18, weight='bold')

    valid_stats = [s for s in all_stats.values() if s is not None]
    overall_pass = bool(valid_stats) and all(s['median_rel'] < 0.01 for s in valid_stats)

    lines = [
        "OVERALL VALIDATION RESULT:",
        "=" * 70,
        "",
        f"Status: {'✅ PASS' if overall_pass else '⚠️ NEEDS REVIEW'}",
        "",
        "=" * 70,
        "COMPONENT RESULTS:",
        "",
    ]
    for field in FIELD_ORDER:
        stats = all_stats.get(field)
        if stats is None:
            lines.extend([f"{field}: no wet cells to compare", ""])
            continue
        status = ("✅ EXCELLENT" if stats['median_rel'] < 0.001 else
                   "✅ GOOD" if stats['median_rel'] < 0.01 else
                   "⚠️ CHECK")
        lines.extend([
            f"{field}:  {status}",
            f"  Median rel error: {stats['median_rel']:.4%}    Max |diff|: {stats['max_abs']:.4e}",
            f"  Fraction >1% rel: {stats['frac_gt_1pct']:.4%}",
            "",
        ])

    lines.extend([
        "=" * 70,
        "PROVENANCE:",
        "",
        f"UUID Match: {'✅ Yes' if metadata['uuid_match'] else '⚠️ No'}",
        f"MITgcm UUID: {metadata['uuid1']}",
        f"Python UUID: {metadata['uuid2']}",
        "",
        "=" * 70,
        "ACCEPTANCE CRITERIA (mirrors generate_kpp_validation_report.py's own):",
        "",
        "✅ EXCELLENT:  median rel error < 0.1%",
        "✅ GOOD:       median rel error < 1.0%",
        "⚠️ CHECK:      median rel error >= 1.0% -- may be a real, already-",
        "              characterized gap (see closed_issues.md), not necessarily",
        "              a new defect; this report states the number, not the cause.",
    ])
    fig.text(0.5, 0.87, '\n'.join(lines), ha='center', va='top', fontsize=9, family='monospace')
    plt.axis('off')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def generate_pdf_report(ds1: xr.Dataset, ds2: xr.Dataset, metadata: Dict,
                         all_stats: Dict[str, Optional[Dict]], output_pdf: Path) -> None:
    """Generate the multi-page GGL90 validation PDF report."""
    print(f"\n{'=' * 70}")
    print("Generating PDF report...")
    print(f"{'=' * 70}")

    single_column = len(ds1.x) == 1 and len(ds1.y) == 1

    with PdfPages(output_pdf) as pdf:
        _add_title_page(pdf, ds1, ds2, metadata)
        _add_statistics_page(pdf, all_stats)

        for field in FIELD_ORDER:
            stats = all_stats.get(field)
            if stats is None:
                continue
            _add_field_scatter_page(pdf, ds1, ds2, field, stats)
            if single_column:
                _add_field_profile_page(pdf, ds1, ds2, field)

        _add_summary_page(pdf, metadata, all_stats)

    print(f"  ✅ Report saved: {output_pdf}")
    print(f"  Size: {output_pdf.stat().st_size / 1024:.1f} KB")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nError: Insufficient arguments")
        print("\nUsage: python generate_ggl90_validation_report.py <mitgcm_output.nc> <python_output.nc> [report.pdf]")
        sys.exit(1)

    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])

    if not file1.exists():
        print(f"Error: File not found: {file1}")
        sys.exit(1)
    if not file2.exists():
        print(f"Error: File not found: {file2}")
        sys.exit(1)

    if len(sys.argv) >= 4:
        output_pdf = Path(sys.argv[3])
    else:
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        output_pdf = Path(f'ggl90_validation_report_{timestamp}.pdf')

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("GGL90 Validation Report Generator")
    print("=" * 70)
    print(f"\nMITgcm output: {file1}")
    print(f"Python output: {file2}")
    print(f"Report:        {output_pdf}")

    ds1, ds2, metadata = load_and_validate_datasets(file1, file2)

    all_stats: Dict[str, Optional[Dict]] = {}
    for field in FIELD_ORDER:
        if field not in ds1.data_vars or field not in ds2.data_vars:
            print(f"  ⚠️  {field}: missing from one or both datasets -- skipping")
            all_stats[field] = None
            continue
        all_stats[field] = compute_field_statistics(ds1, ds2, field)

    generate_pdf_report(ds1, ds2, metadata, all_stats, output_pdf)

    print(f"\n{'=' * 70}")
    print("✅ Validation report complete!")
    print(f"{'=' * 70}")
    print(f"\nReport: {output_pdf}")

    valid_stats = [s for s in all_stats.values() if s is not None]
    if valid_stats:
        overall_pass = all(s['median_rel'] < 0.01 for s in valid_stats)
        if overall_pass:
            print("\nResult: ✅ VALIDATION PASSED")
        else:
            print("\nResult: ⚠️  NEEDS REVIEW - see report for details")


if __name__ == '__main__':
    main()
