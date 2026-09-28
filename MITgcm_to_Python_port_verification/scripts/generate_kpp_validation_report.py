#!/usr/bin/env python3
"""
Generate comprehensive KPP validation report comparing MITgcm and Python outputs.

This consolidated script combines comparison, statistics, and visualization into a
single PDF report showing:
  - Provenance tracking (UUID verification)
  - HBL time series, scatter plots, and statistics
  - Mixing coefficient profiles and comparisons
  - Boundary layer vs background statistics
  - Overall validation assessment

Usage:
  python generate_kpp_validation_report.py <mitgcm_output.nc> <python_output.nc> [report.pdf]

Examples:
  python generate_kpp_validation_report.py \\
    KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc \\
    KPP_port_validation/outputs_from_python/python_kpp_outputs_11k_1D.nc

  python generate_kpp_validation_report.py \\
    outputs/kpp_output_lab_sea_20260819.nc \\
    outputs/kpp_output_lab_sea_20260819_python.nc \\
    reports/validation_lab_sea.pdf
"""

import sys
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
from typing import Dict, Tuple


def load_and_validate_datasets(file1: Path, file2: Path) -> Tuple[xr.Dataset, xr.Dataset, Dict]:
    """
    Load two output datasets and perform provenance checks.

    Returns
    -------
    ds1, ds2 : xr.Dataset
        The two datasets
    metadata : dict
        Provenance and metadata information
    """
    print(f"Loading MITgcm outputs: {file1.name}")
    ds1 = xr.open_dataset(file1)

    print(f"Loading Python outputs:  {file2.name}")
    ds2 = xr.open_dataset(file2)

    metadata = {
        'file1': str(file1),
        'file2': str(file2),
        'label1': "MITgcm",
        'label2': "Python",
    }

    # UUID provenance check
    uuid1 = ds1.attrs.get('input_uuid', 'N/A')
    uuid2 = ds2.attrs.get('input_uuid', 'N/A')
    metadata['uuid1'] = uuid1
    metadata['uuid2'] = uuid2
    metadata['uuid_match'] = (uuid1 == uuid2) and (uuid1 != 'N/A')

    print(f"\nProvenance Check:")
    print(f"  MITgcm input_uuid: {uuid1}")
    print(f"  Python input_uuid: {uuid2}")
    if metadata['uuid_match']:
        print(f"  ✅ UUIDs match - same inputs used")
    else:
        print(f"  ⚠️  UUID mismatch - different inputs!")

    # Dimensions check
    print(f"\nDimensions:")
    print(f"  MITgcm: time={len(ds1.time)}, x={len(ds1.x)}, y={len(ds1.y)}, z={len(ds1.z)}")
    print(f"  Python: time={len(ds2.time)}, x={len(ds2.x)}, y={len(ds2.y)}, z={len(ds2.z)}")

    # 1DMIX-044 fix: a Python output covering only a leading subsample of
    # MITgcm's own full time range (e.g. run_kpp_from_netcdf_input.py run
    # with --last set, as this project's own lab_sea_6mo regression test
    # does for tractability -- a 222 MB, heavily-chunked capture where the
    # untruncated 4368-timestep replay is impractical to regenerate on every
    # report refresh) previously crashed this function's caller with a
    # numpy broadcast ValueError the first time this script was ever run
    # against such a pair (confirmed directly: ds1.sizes != ds2.sizes was
    # already detected and warned about, but nothing downstream acted on
    # it). Mirrors run_kpp_from_netcdf_input.py::main's own established
    # slicing convention for its "Quick Comparison" section
    # (`mit_ds.isel(time=slice(first_t, last_t + 1))`): if the Python
    # dataset's time axis is a strict prefix of MITgcm's, restrict MITgcm to
    # that same prefix before any statistic is computed, rather than either
    # crashing or silently padding/truncating incorrectly.
    if len(ds1.time) != len(ds2.time):
        if len(ds2.time) < len(ds1.time):
            n_mitgcm_full, n_python = len(ds1.time), len(ds2.time)
            print(f"  ℹ️  Python output covers only the first {n_python} of "
                  f"{n_mitgcm_full} MITgcm timesteps -- restricting MITgcm to that "
                  "same leading subsample for comparison.")
            ds1 = ds1.isel(time=slice(0, n_python))
            metadata['time_subsample_note'] = (
                f"Python output covers only the first {n_python} of "
                f"{n_mitgcm_full} timesteps; MITgcm restricted to the same "
                "leading subsample for this comparison."
            )
        else:
            print("  ⚠️  WARNING: Python output has MORE timesteps than MITgcm -- "
                  "cannot restrict; comparison will fail downstream.")

    if ds1.sizes != ds2.sizes:
        print(f"  ⚠️  WARNING: Dimension mismatch!")

    return ds1, ds2, metadata


def compute_hbl_statistics(ds1: xr.Dataset, ds2: xr.Dataset) -> Dict:
    """
    Compute HBL comparison statistics.

    Returns
    -------
    dict
        HBL statistics including mean, max, RMS differences
    """
    print(f"\n{'='*70}")
    print(f"HBL (Boundary Layer Depth) Comparison")
    print(f"{'='*70}")

    hbl1 = ds1.hbl.values
    hbl2 = ds2.hbl.values
    hbl_diff = hbl2 - hbl1

    # Remove NaN values
    mask = ~(np.isnan(hbl1) | np.isnan(hbl2))
    hbl_diff_valid = hbl_diff[mask]

    if len(hbl_diff_valid) == 0:
        print("  No valid HBL data to compare")
        return None

    stats = {
        'mean_abs_diff': float(np.mean(np.abs(hbl_diff_valid))),
        'max_abs_diff': float(np.max(np.abs(hbl_diff_valid))),
        'rms_diff': float(np.sqrt(np.mean(hbl_diff_valid**2))),
        'mean_rel_error': float(100 * np.mean(np.abs(hbl_diff_valid) / hbl1[mask])),
        'median_rel_error': float(100 * np.median(np.abs(hbl_diff_valid) / hbl1[mask])),
        'n_points': int(np.sum(mask)),
        'hbl1_min': float(hbl1[mask].min()),
        'hbl1_max': float(hbl1[mask].max()),
        'hbl2_min': float(hbl2[mask].min()),
        'hbl2_max': float(hbl2[mask].max()),
    }

    print(f"  Mean |difference|:     {stats['mean_abs_diff']:.6f} m")
    print(f"  Max |difference|:      {stats['max_abs_diff']:.6f} m")
    print(f"  RMS difference:        {stats['rms_diff']:.6f} m")
    print(f"  Mean relative error:   {stats['mean_rel_error']:.4f}%")
    print(f"  Median relative error: {stats['median_rel_error']:.4f}%")
    print(f"  Points compared:       {stats['n_points']}")

    if stats['max_abs_diff'] < 0.1:
        print(f"  ✅ EXCELLENT - within 10 cm")
    elif stats['max_abs_diff'] < 1.0:
        print(f"  ✅ GOOD - within 1 m")
    else:
        print(f"  ⚠️  CHECK - differences > 1 m")

    return stats


def compute_mixing_statistics(ds1: xr.Dataset, ds2: xr.Dataset) -> Dict:
    """
    Compute mixing coefficient comparison statistics.

    Returns
    -------
    dict
        Statistics for visc_az, diff_kz_s, diff_kz_t, ghat
    """
    print(f"\n{'='*70}")
    print(f"Mixing Coefficients Comparison")
    print(f"{'='*70}")

    stats = {}

    # Mixing coefficients (where active mixing occurs)
    for var in ['visc_az', 'diff_kz_s', 'diff_kz_t']:
        if var not in ds1.data_vars or var not in ds2.data_vars:
            continue

        v1 = ds1[var].values
        v2 = ds2[var].values

        # Compare where mixing is active (> background threshold)
        mask = v1 > 1e-6

        if np.any(mask):
            v1_masked = v1[mask]
            v2_masked = v2[mask]

            abs_diff = np.abs(v2_masked - v1_masked)
            rel_diff = 100 * abs_diff / np.abs(v1_masked)

            stats[var] = {
                'median_rel_error': float(np.median(rel_diff)),
                'mean_rel_error': float(np.mean(rel_diff)),
                'max_rel_error': float(np.max(rel_diff)),
                'p95_rel_error': float(np.percentile(rel_diff, 95)),
                'median_abs_diff': float(np.median(abs_diff)),
                'n_points': int(np.sum(mask)),
            }

            print(f"\n{var} (active mixing, >{1e-6:.0e} m²/s):")
            print(f"  Median relative error: {stats[var]['median_rel_error']:.6f}%")
            print(f"  Mean relative error:   {stats[var]['mean_rel_error']:.6f}%")
            print(f"  Max relative error:    {stats[var]['max_rel_error']:.6f}%")
            print(f"  95th percentile error: {stats[var]['p95_rel_error']:.6f}%")
            print(f"  Median absolute diff:  {stats[var]['median_abs_diff']:.6e} m²/s")
            print(f"  Points compared:       {stats[var]['n_points']}")

            if stats[var]['median_rel_error'] < 0.1:
                print(f"  ✅ EXCELLENT - within 0.1%")
            elif stats[var]['median_rel_error'] < 1.0:
                print(f"  ✅ GOOD - within 1%")
            else:
                print(f"  ⚠️  CHECK - median error > 1%")

    # Ghat (nonlocal transport)
    if 'ghat' in ds1.data_vars and 'ghat' in ds2.data_vars:
        print(f"\nghat (nonlocal transport):")

        ghat1 = ds1.ghat.values
        ghat2 = ds2.ghat.values

        mask = np.abs(ghat1) > 1e-10

        if np.any(mask):
            ghat1_masked = ghat1[mask]
            ghat2_masked = ghat2[mask]

            abs_diff = np.abs(ghat2_masked - ghat1_masked)
            rel_diff = 100 * abs_diff / np.abs(ghat1_masked)

            stats['ghat'] = {
                'median_rel_error': float(np.median(rel_diff)),
                'mean_rel_error': float(np.mean(rel_diff)),
                'max_rel_error': float(np.max(rel_diff)),
                'n_points': int(np.sum(mask)),
            }

            print(f"  Median relative error: {stats['ghat']['median_rel_error']:.6f}%")
            print(f"  Mean relative error:   {stats['ghat']['mean_rel_error']:.6f}%")
            print(f"  Points compared:       {stats['ghat']['n_points']}")

    return stats


def generate_pdf_report(ds1: xr.Dataset, ds2: xr.Dataset, metadata: Dict,
                        hbl_stats: Dict, mixing_stats: Dict, output_pdf: Path):
    """
    Generate comprehensive PDF validation report.

    Parameters
    ----------
    ds1, ds2 : xr.Dataset
        MITgcm and Python output datasets
    metadata : dict
        Provenance and file metadata
    hbl_stats : dict
        HBL comparison statistics
    mixing_stats : dict
        Mixing coefficient statistics
    output_pdf : Path
        Output PDF filename
    """
    print(f"\n{'='*70}")
    print(f"Generating PDF report...")
    print(f"{'='*70}")

    with PdfPages(output_pdf) as pdf:
        # ============================================================
        # Title Page
        # ============================================================
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.75, 'KPP Validation Report',
                ha='center', va='center', fontsize=28, weight='bold')
        fig.text(0.5, 0.68, 'MITgcm vs Python Port Comparison',
                ha='center', va='center', fontsize=16)

        # Metadata
        y_pos = 0.55
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
        ]
        # 1DMIX-044: surface load_and_validate_datasets's leading-time-
        # subsample restriction (see that function's own docstring/comment)
        # on the title page itself, not only in stdout, so a PDF reader
        # sees the report covers fewer than the capture's full timestep
        # count.
        if 'time_subsample_note' in metadata:
            info_text.extend(["", f"Note: {metadata['time_subsample_note']}"])

        fig.text(0.5, y_pos, '\n'.join(info_text),
                ha='center', va='top', fontsize=11, family='monospace')

        plt.axis('off')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

        # ============================================================
        # HBL Comparison Page
        # ============================================================
        if hbl_stats is not None:
            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            fig.suptitle('Boundary Layer Depth (HBL) Comparison', fontsize=14, weight='bold')

            hbl1 = ds1.hbl.values.flatten()
            hbl2 = ds2.hbl.values.flatten()

            # Remove NaNs
            mask = ~(np.isnan(hbl1) | np.isnan(hbl2))
            hbl1_valid = hbl1[mask]
            hbl2_valid = hbl2[mask]

            # Time series (if 1D column)
            if len(ds1.x) == 1 and len(ds1.y) == 1:
                ax = axes[0, 0]
                ax.plot(ds1.time, ds1.hbl.isel(x=0, y=0), 'o-', label='MITgcm',
                       linewidth=2, markersize=4, alpha=0.7)
                ax.plot(ds2.time, ds2.hbl.isel(x=0, y=0), 's-', label='Python',
                       linewidth=2, markersize=4, alpha=0.7)
                ax.set_xlabel('Time', fontsize=10)
                ax.set_ylabel('HBL (m)', fontsize=10)
                ax.set_title('HBL Time Series', fontsize=11, weight='bold')
                ax.legend(fontsize=9)
                ax.grid(True, alpha=0.3)
            else:
                # For 2D/3D, show histogram of MITgcm HBL
                ax = axes[0, 0]
                ax.hist(hbl1_valid, bins=30, edgecolor='black', alpha=0.7)
                ax.set_xlabel('HBL (m)', fontsize=10)
                ax.set_ylabel('Frequency', fontsize=10)
                ax.set_title('MITgcm HBL Distribution', fontsize=11, weight='bold')
                ax.grid(True, alpha=0.3)

            # Scatter plot
            ax = axes[0, 1]
            ax.scatter(hbl1_valid, hbl2_valid, alpha=0.5, s=20, c='blue', edgecolors='none')
            lim_min = min(hbl1_valid.min(), hbl2_valid.min())
            lim_max = max(hbl1_valid.max(), hbl2_valid.max())
            ax.plot([lim_min, lim_max], [lim_min, lim_max], 'r--',
                   linewidth=2, label='1:1 line')
            ax.set_xlabel('MITgcm HBL (m)', fontsize=10)
            ax.set_ylabel('Python HBL (m)', fontsize=10)
            ax.set_title('HBL Scatter Plot', fontsize=11, weight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.axis('equal')

            # Difference histogram
            ax = axes[1, 0]
            diff = hbl2_valid - hbl1_valid
            ax.hist(diff, bins=30, edgecolor='black', alpha=0.7)
            ax.axvline(0, color='r', linestyle='--', linewidth=2, label='Zero')
            ax.axvline(np.mean(diff), color='green', linestyle='--',
                      linewidth=2, label=f'Mean={np.mean(diff):.3f}')
            ax.set_xlabel('Difference: Python - MITgcm (m)', fontsize=10)
            ax.set_ylabel('Frequency', fontsize=10)
            ax.set_title('HBL Difference Distribution', fontsize=11, weight='bold')
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)

            # Statistics text
            ax = axes[1, 1]
            ax.axis('off')
            stats_text = [
                'HBL Statistics:',
                '─' * 35,
                f"Mean |diff|:       {hbl_stats['mean_abs_diff']:.6f} m",
                f"Max |diff|:        {hbl_stats['max_abs_diff']:.6f} m",
                f"RMS diff:          {hbl_stats['rms_diff']:.6f} m",
                '',
                f"Mean rel error:    {hbl_stats['mean_rel_error']:.4f}%",
                f"Median rel error:  {hbl_stats['median_rel_error']:.4f}%",
                '',
                f"Points compared:   {hbl_stats['n_points']}",
                '',
                '─' * 35,
                'Range:',
                f"MITgcm: {hbl_stats['hbl1_min']:.1f} – {hbl_stats['hbl1_max']:.1f} m",
                f"Python: {hbl_stats['hbl2_min']:.1f} – {hbl_stats['hbl2_max']:.1f} m",
                '',
                '─' * 35,
                'Assessment:',
                '✅ EXCELLENT' if hbl_stats['max_abs_diff'] < 0.1 else
                '✅ GOOD' if hbl_stats['max_abs_diff'] < 1.0 else
                '⚠️ CHECK'
            ]
            ax.text(0.1, 0.95, '\n'.join(stats_text), transform=ax.transAxes,
                   fontsize=9, verticalalignment='top', family='monospace')

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close()

        # ============================================================
        # Mixing Coefficient Profiles (if 1D column)
        # ============================================================
        if len(ds1.x) == 1 and len(ds1.y) == 1:
            for var in ['visc_az', 'diff_kz_s', 'diff_kz_t']:
                if var not in ds1.data_vars or var not in ds2.data_vars:
                    continue

                fig, axes = plt.subplots(1, 3, figsize=(11, 8.5), sharey=True)
                fig.suptitle(f'{var.upper()} Vertical Profiles', fontsize=14, weight='bold')

                depth = ds1.depth_iface.values if 'depth_iface' in ds1.coords else ds1.depth.values

                # Select timesteps to plot (max 5)
                n_time = len(ds1.time)
                time_indices = np.linspace(0, n_time-1, min(5, n_time), dtype=int)
                colors = plt.cm.viridis(np.linspace(0, 1, len(time_indices)))

                for idx, t_idx in enumerate(time_indices):
                    v1 = ds1[var].isel(time=t_idx, x=0, y=0).values
                    v2 = ds2[var].isel(time=t_idx, x=0, y=0).values

                    # MITgcm profile
                    axes[0].plot(v1, depth, linewidth=2, color=colors[idx],
                                label=f't={t_idx}' if len(time_indices) <= 5 else None)

                    # Python profile
                    axes[1].plot(v2, depth, linewidth=2, color=colors[idx])

                    # Difference
                    axes[2].plot(v2 - v1, depth, linewidth=2, color=colors[idx])

                axes[0].set_title('MITgcm', fontsize=11, weight='bold')
                axes[0].set_xlabel(f'{var} (m²/s)', fontsize=10)
                axes[0].set_ylabel('Depth (m)', fontsize=10)
                axes[0].set_xscale('log')
                axes[0].grid(True, alpha=0.3)
                if len(time_indices) <= 5:
                    axes[0].legend(fontsize=8)

                axes[1].set_title('Python', fontsize=11, weight='bold')
                axes[1].set_xlabel(f'{var} (m²/s)', fontsize=10)
                axes[1].set_xscale('log')
                axes[1].grid(True, alpha=0.3)

                axes[2].set_title('Difference (Python - MITgcm)', fontsize=11, weight='bold')
                axes[2].set_xlabel(f'Δ{var} (m²/s)', fontsize=10)
                axes[2].axvline(0, color='r', linestyle='--', linewidth=2, alpha=0.7)
                axes[2].ticklabel_format(style='scientific', axis='x', scilimits=(0,0))
                axes[2].grid(True, alpha=0.3)

                plt.tight_layout()
                pdf.savefig(fig, bbox_inches='tight')
                plt.close()

        # ============================================================
        # Mixing Statistics Summary Page
        # ============================================================
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.95, 'Mixing Coefficients Statistics',
                ha='center', va='top', fontsize=18, weight='bold')

        stats_lines = [
            "Active Mixing Regions (coefficient > 1e-6 m²/s)",
            "=" * 70,
            "",
        ]

        for var, var_stats in mixing_stats.items():
            var_label = var.upper()
            status = ("✅ EXCELLENT" if var_stats['median_rel_error'] < 0.1 else
                     "✅ GOOD" if var_stats['median_rel_error'] < 1.0 else
                     "⚠️ CHECK")

            stats_lines.extend([
                f"{var_label}:                                   {status}",
                f"  Median relative error:           {var_stats['median_rel_error']:.6f}%",
                f"  Mean relative error:             {var_stats['mean_rel_error']:.6f}%",
            ])

            if 'max_rel_error' in var_stats:
                stats_lines.append(f"  Max relative error:              {var_stats['max_rel_error']:.6f}%")
            if 'p95_rel_error' in var_stats:
                stats_lines.append(f"  95th percentile error:           {var_stats['p95_rel_error']:.6f}%")
            if 'median_abs_diff' in var_stats:
                stats_lines.append(f"  Median absolute diff:            {var_stats['median_abs_diff']:.6e} m²/s")

            stats_lines.extend([
                f"  Points compared:                 {var_stats['n_points']}",
                "",
            ])

        fig.text(0.5, 0.85, '\n'.join(stats_lines),
                ha='center', va='top', fontsize=9, family='monospace')

        plt.axis('off')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

        # ============================================================
        # Validation Summary Page
        # ============================================================
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.95, 'Validation Summary & Assessment',
                ha='center', va='top', fontsize=18, weight='bold')

        # Overall pass/fail assessment
        hbl_pass = hbl_stats is not None and hbl_stats['max_abs_diff'] < 1.0
        mixing_pass = all(s['median_rel_error'] < 1.0 for s in mixing_stats.values())
        overall_pass = hbl_pass and mixing_pass

        summary_lines = [
            "OVERALL VALIDATION RESULT:",
            "=" * 70,
            "",
            f"Status: {'✅ PASS' if overall_pass else '⚠️ NEEDS REVIEW'}",
            "",
            "=" * 70,
            "COMPONENT RESULTS:",
            "",
        ]

        if hbl_stats is not None:
            hbl_status = ("✅ EXCELLENT" if hbl_stats['max_abs_diff'] < 0.1 else
                         "✅ GOOD" if hbl_stats['max_abs_diff'] < 1.0 else
                         "⚠️ CHECK")
            summary_lines.extend([
                f"HBL (Boundary Layer Depth):                    {hbl_status}",
                f"  Max difference:                              {hbl_stats['max_abs_diff']:.6f} m",
                f"  Mean relative error:                         {hbl_stats['mean_rel_error']:.4f}%",
                "",
            ])

        for var, var_stats in mixing_stats.items():
            var_status = ("✅ EXCELLENT" if var_stats['median_rel_error'] < 0.1 else
                         "✅ GOOD" if var_stats['median_rel_error'] < 1.0 else
                         "⚠️ CHECK")
            summary_lines.extend([
                f"{var.upper()}:                                          {var_status}",
                f"  Median relative error:                       {var_stats['median_rel_error']:.6f}%",
                "",
            ])

        summary_lines.extend([
            "=" * 70,
            "PROVENANCE:",
            "",
            f"UUID Match:                                      {'✅ Yes' if metadata['uuid_match'] else '⚠️ No'}",
            f"MITgcm UUID:     {metadata['uuid1'][:32]}...",
            f"Python UUID:     {metadata['uuid2'][:32]}...",
            "",
            "=" * 70,
            "ACCEPTANCE CRITERIA:",
            "",
            "✅ EXCELLENT:  HBL < 0.1m, mixing < 0.1% error",
            "✅ GOOD:       HBL < 1.0m, mixing < 1.0% error",
            "⚠️ CHECK:      Exceeds thresholds - investigate",
        ])

        fig.text(0.5, 0.85, '\n'.join(summary_lines),
                ha='center', va='top', fontsize=9, family='monospace')

        plt.axis('off')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    print(f"  ✅ Report saved: {output_pdf}")
    print(f"  Size: {output_pdf.stat().st_size / 1024:.1f} KB")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nError: Insufficient arguments")
        print("\nUsage: python generate_kpp_validation_report.py <mitgcm_output.nc> <python_output.nc> [report.pdf]")
        sys.exit(1)

    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])

    if not file1.exists():
        print(f"Error: File not found: {file1}")
        sys.exit(1)

    if not file2.exists():
        print(f"Error: File not found: {file2}")
        sys.exit(1)

    # Determine output filename
    if len(sys.argv) >= 4:
        output_pdf = Path(sys.argv[3])
    else:
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        output_pdf = Path(f'kpp_validation_report_{timestamp}.pdf')

    # Ensure output directory exists
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("KPP Validation Report Generator")
    print("=" * 70)
    print(f"\nMITgcm output: {file1}")
    print(f"Python output: {file2}")
    print(f"Report:        {output_pdf}")

    # Load datasets and check provenance
    ds1, ds2, metadata = load_and_validate_datasets(file1, file2)

    # Compute statistics
    hbl_stats = compute_hbl_statistics(ds1, ds2)
    mixing_stats = compute_mixing_statistics(ds1, ds2)

    # Generate PDF report
    generate_pdf_report(ds1, ds2, metadata, hbl_stats, mixing_stats, output_pdf)

    print(f"\n{'='*70}")
    print(f"✅ Validation report complete!")
    print(f"{'='*70}")
    print(f"\nReport: {output_pdf}")

    # Overall assessment
    if hbl_stats:
        hbl_pass = hbl_stats['max_abs_diff'] < 1.0
        mixing_pass = all(s['median_rel_error'] < 1.0 for s in mixing_stats.values())

        if hbl_pass and mixing_pass:
            print("\nResult: ✅ VALIDATION PASSED")
        else:
            print("\nResult: ⚠️  NEEDS REVIEW - see report for details")


if __name__ == '__main__':
    main()
