#!/usr/bin/env python3
"""
Unified plotter for 1D mixing-model output.

Reads a diagnostics NPZ file (written by DiagnosticsManager.save_to_file) and
produces two figures:

  Figure 1 -- Vertical profiles at N equally-spaced times (default 5). One
              subplot per depth-resolved variable; each curve is a snapshot,
              colored light -> dark with increasing time.

  Figure 2 -- Depth-vs-time filled contour plots, one subplot per depth-resolved
              variable, using ALL saved records.

The primary panel set is standardized across schemes so the same quantities
appear in the same subplot positions for KPP and GGL90 runs.

Vertical staggering (see MITGCM_STAGGERING.md): tracer/velocity/TKE fields are at
cell CENTERS (plotted at `depth`); mixing coefficients are at cell top FACES
(interfaces). The plotter plots every depth-resolved field against the cell-center
depth axis for a common, readable vertical coordinate; this is a display choice
and does not change the data.

Usage
-----
    python main/unified_plotter.py output/kpp_experiment.npz
    python main/unified_plotter.py output/ggl90_experiment.npz --n-profiles 7
    python main/unified_plotter.py output/kpp_experiment.npz --save fig --no-show
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import matplotlib

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import TwoSlopeNorm


# Fields that are never plotted as depth profiles/contours (bookkeeping or
# scalar-in-depth diagnostics). Everything else that is 2D (time, depth) is
# auto-plotted.
_NON_FIELD_KEYS = {
    "time_seconds", "depth", "cell_thickness", "scheme",
}

# Preferred display order and pretty labels/units for known variables. Unknown
# variables still plot, appended after these in file order.
_LABELS: Dict[str, Tuple[str, str]] = {
    "theta":         ("Potential temperature", "°C"),
    "salt":          ("Salinity", "psu"),
    "u_vel":         ("Zonal velocity", "m/s"),
    "v_vel":         ("Meridional velocity", "m/s"),
    "tke":           ("Turbulent kinetic energy", "m²/s²"),
    "visc_az":       ("Vertical viscosity", "m²/s"),
    "diff_kz_t":     ("Temp diffusivity", "m²/s"),
    "diff_kz_s":     ("Salt diffusivity", "m²/s"),
    "diff_kz":       ("Diffusivity", "m²/s"),
    "ghat":          ("Nonlocal transport ghat", "s/m²"),
    "mixing_length": ("Mixing length", "m"),
    "n_square":      ("Buoyancy freq. N²", "s⁻²"),
    "potential_density": ("Potential density", "kg/m³"),
    "drho_dz":       ("Vertical density gradient", "kg/m⁴"),
    "shear_s2":      ("Vertical shear S²", "s⁻²"),
    "shear_square":  ("Shear² S²", "s⁻²"),
    "shear_sq":      ("Shear²", "m²/s²"),
    "bulk_ri":       ("Bulk Richardson no.", "-"),
}

# Signed fields get a diverging colormap centered on zero (velocity components).
# Everything else is a magnitude field -> sequential colormap.
_DIVERGING_FIELDS = {"u_vel", "v_vel"}

_PREFERRED_ORDER = [
    "theta", "salt", "u_vel", "v_vel", "tke",
    "visc_az", "diff_kz_t", "diff_kz_s", "diff_kz", "ghat",
    "mixing_length", "n_square", "shear_square", "shear_sq", "bulk_ri",
    "potential_density", "drho_dz", "shear_s2",
]

_STANDARD_PLOT_FIELDS = [
    "theta",
    "salt",
    "u_vel",
    "visc_az",
    "diff_kz_t",
    "shear_s2",
    "potential_density",
    "drho_dz",
]

_BOTTOM_ROW_BY_SCHEME = {
    "kpp": "ghat",
    "ggl90": "tke",
}


def _label(key: str) -> str:
    name, unit = _LABELS.get(key, (key, ""))
    return f"{name} [{unit}]" if unit else name


def load_output(npz_path: Path) -> Dict:
    """Load a diagnostics NPZ into a plain dict (arrays + scheme string)."""
    npz_path = Path(npz_path)
    if not npz_path.exists():
        raise FileNotFoundError(f"Output file not found: {npz_path}")
    with np.load(npz_path, allow_pickle=True) as f:
        data = {k: f[k] for k in f.files}
    return data


def _detect_depth_fields(data: Dict) -> List[str]:
    """Return depth-resolved 2D field keys (shape (nt_i, nz)) in display order."""
    nz = len(data["depth"])
    fields = [
        k for k, v in data.items()
        if k not in _NON_FIELD_KEYS
        and isinstance(v, np.ndarray)
        and v.ndim == 2
        and v.shape[1] == nz
    ]

    # Keep plot layout fixed across schemes whenever these standard diagnostics
    # are available (row 2: viscosity/diffusivity/shear; final row: density terms).
    standard = [k for k in _STANDARD_PLOT_FIELDS if k in fields]
    if standard:
        scheme = str(data.get("scheme", "")).strip().lower()
        bottom_key = _BOTTOM_ROW_BY_SCHEME.get(scheme)
        if bottom_key in fields:
            standard.append(bottom_key)
        return standard

    # order: preferred first (if present), then any extras in file order
    ordered = [k for k in _PREFERRED_ORDER if k in fields]
    ordered += [k for k in fields if k not in ordered]
    return ordered


def _time_axis_for(field: np.ndarray, time_seconds: np.ndarray) -> np.ndarray:
    """Align a field's leading axis to the tail of the time vector.

    State variables carry the initial condition (nt records); mixing/diagnostic
    fields skip it (nt-1). In both cases the field corresponds to the LAST
    field.shape[0] time points.
    """
    nrec = field.shape[0]
    return time_seconds[-nrec:]


def _grid_shape(n: int) -> Tuple[int, int]:
    """Choose a roughly-square subplot grid for n panels."""
    ncols = int(np.ceil(np.sqrt(n)))
    nrows = int(np.ceil(n / ncols))
    return nrows, ncols


def _days(time_seconds: np.ndarray) -> np.ndarray:
    return time_seconds / 86400.0


def plot_profiles(
    data: Dict,
    n_profiles: int = 5,
    fields: Optional[List[str]] = None,
) -> plt.Figure:
    """Figure 1: vertical profiles at N equally-spaced times.

    Each subplot is one variable; each line a time snapshot colored by time.
    """
    depth = data["depth"]
    tsec = data["time_seconds"]
    if fields is None:
        fields = _detect_depth_fields(data)

    nrows, ncols = _grid_shape(len(fields))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(3.4 * ncols, 4.2 * nrows), squeeze=False
    )
    axes_flat = axes.ravel()

    cmap = matplotlib.colormaps["viridis"]

    # Only the leftmost column carries the depth axis label (avoid overlap with
    # the neighboring subplot's data).
    leftmost = set(range(0, len(axes_flat), ncols))

    # Choose which time indices to draw, from the full time vector; each field
    # is then matched to its own available records.
    nt = len(tsec)
    n_sel = min(n_profiles, nt)
    sel_full = np.unique(np.linspace(0, nt - 1, n_sel).round().astype(int))
    sel_days = _days(tsec)[sel_full]
    tmin, tmax = float(sel_days[0]), float(sel_days[-1])
    tspan = (tmax - tmin) or 1.0

    for ipanel, (ax, key) in enumerate(zip(axes_flat, fields)):
        field = data[key]
        # map global selected indices onto this field's row indices
        offset = nt - field.shape[0]  # 0 for state vars, 1 for mixing fields
        for gi, day in zip(sel_full, sel_days):
            ri = gi - offset
            if ri < 0 or ri >= field.shape[0]:
                continue
            color = cmap((day - tmin) / tspan)
            ax.plot(field[ri], depth, color=color, lw=1.8,
                    label=f"{day:.2f} d")
        ax.set_title(_label(key), fontsize=10)
        if ipanel in leftmost:
            ax.set_ylabel("Depth [m]")
        ax.grid(True, alpha=0.25, lw=0.6)

    # hide any unused panels
    for ax in axes_flat[len(fields):]:
        ax.set_visible(False)

    # single shared colorbar for time
    sm = cm.ScalarMappable(cmap=cmap,
                           norm=plt.Normalize(vmin=tmin, vmax=tmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes.ravel().tolist(), shrink=0.6,
                        pad=0.02, location="right")
    cbar.set_label("Time [days]")

    scheme = str(data.get("scheme", ""))
    fig.suptitle(f"{scheme}  —  vertical profiles "
                 f"({len(sel_full)} times)", fontsize=13)
    return fig


def plot_contours(
    data: Dict,
    fields: Optional[List[str]] = None,
    n_levels: int = 21,
) -> plt.Figure:
    """Figure 2: depth-vs-time filled contours using all saved records."""
    depth = data["depth"]
    tsec = data["time_seconds"]
    if fields is None:
        fields = _detect_depth_fields(data)

    nrows, ncols = _grid_shape(len(fields))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(4.2 * ncols, 3.6 * nrows), squeeze=False
    )
    axes_flat = axes.ravel()

    for ax, key in zip(axes_flat, fields):
        field = data[key]
        tdays = _days(_time_axis_for(field, tsec))
        T, Z = np.meshgrid(tdays, depth, indexing="ij")

        signed = key in _DIVERGING_FIELDS
        finite = field[np.isfinite(field)]
        if signed and finite.size and np.any(finite < 0) and np.any(finite > 0):
            vmax = np.max(np.abs(finite))
            norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
            cmap = "RdBu_r"
            levels = np.linspace(-vmax, vmax, n_levels)
        else:
            norm = None
            cmap = "viridis"
            if finite.size and finite.min() != finite.max():
                levels = np.linspace(finite.min(), finite.max(), n_levels)
            else:
                levels = n_levels

        cf = ax.contourf(T, Z, field, levels=levels, cmap=cmap, norm=norm,
                         extend="both")
        ax.set_title(_label(key), fontsize=10)
        ax.set_xlabel("Time [days]")
        ax.set_ylabel("Depth [m]")
        cbar = fig.colorbar(cf, ax=ax, shrink=0.9, pad=0.02)
        u = _LABELS.get(key, ("", ""))[1]
        if u:
            cbar.set_label(u)

    for ax in axes_flat[len(fields):]:
        ax.set_visible(False)

    scheme = str(data.get("scheme", ""))
    fig.suptitle(f"{scheme}  —  depth vs. time "
                 f"({len(tsec)} records)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def make_figures(
    npz_path: Path,
    n_profiles: int = 5,
) -> Tuple[plt.Figure, plt.Figure]:
    """Load output and build both figures. Returns (profiles_fig, contours_fig)."""
    data = load_output(npz_path)
    fig1 = plot_profiles(data, n_profiles=n_profiles)
    fig2 = plot_contours(data)
    return fig1, fig2


def main():
    parser = argparse.ArgumentParser(
        description="Plot 1D mixing-model output (profiles + depth-time contours)."
    )
    parser.add_argument("npz", type=Path, help="Path to diagnostics NPZ file")
    parser.add_argument("--n-profiles", type=int, default=5,
                        help="Number of equally-spaced profile times (default 5)")
    parser.add_argument("--save", type=str, default=None,
                        help="Path prefix to save figures "
                             "(_profiles.png / _contours.png)")
    parser.add_argument("--no-show", action="store_true",
                        help="Do not open an interactive window")
    args = parser.parse_args()

    if args.no_show:
        matplotlib.use("Agg")

    fig1, fig2 = make_figures(args.npz, n_profiles=args.n_profiles)

    if args.save:
        prefix = Path(args.save)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        p1 = prefix.with_name(prefix.name + "_profiles.png")
        p2 = prefix.with_name(prefix.name + "_contours.png")
        fig1.savefig(p1, dpi=150, bbox_inches="tight")
        fig2.savefig(p2, dpi=150, bbox_inches="tight")
        print(f"Saved {p1}")
        print(f"Saved {p2}")

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
