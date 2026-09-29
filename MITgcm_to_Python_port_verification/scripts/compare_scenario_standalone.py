#!/usr/bin/env python3
"""
Compare a scenario's standalone-Fortran-KPPMIX output (kpp_standalone_output.txt,
from build_and_run.sh) against the Python port's own saved output
(kpp_experiment.npz) -- step (2) vs. step (3) of the three-way method, for
inputs no MITgcm capture has ever produced.

``compare()`` returns a dict keyed by field name
(``visc_az``/``diff_kz_s``/``diff_kz_t``/``ghat``/``hbl``), each value the
per-field statistic dict (``max_abs``/``median_abs``/``p95_abs``/``max_rel``/
``n_gt_1pct``/``n_total``) produced by
``compare_scenario_ggl90_standalone.py::summarize`` -- imported and called
unmodified, not reimplemented here (1DMIX-053). ``summarize`` is entirely
scheme-agnostic (two numpy arrays in, one stats dict out; see its own
docstring/source), so sharing it directly is what makes the KPP and GGL90
scenario reports' numbers mean literally the same thing, not just look alike.
``a`` (the first array) is the Fortran standalone-driver output, used as the
relative-error denominator; ``b`` is the Python port's own saved output --
same convention ``compare_scenario_ggl90_standalone.py::compare`` already
uses.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_scenario_ggl90_standalone import summarize  # noqa: E402


def parse_standalone_output(path: Path, nz: int):
    visc_az = {}
    diff_kz_s = {}
    diff_kz_t = {}
    ghat = {}
    hbl = {}
    t = None
    for line in open(path):
        line = line.strip()
        if line.startswith('TIMESTEP='):
            t = int(line.split(',')[0].split('=')[1])
        elif line.startswith('OUTPUT_MIXING,'):
            parts = line.split(',')
            k = int(parts[3])
            visc_az.setdefault(t, {})[k] = float(parts[4])
            diff_kz_s.setdefault(t, {})[k] = float(parts[5])
            diff_kz_t.setdefault(t, {})[k] = float(parts[6])
            ghat.setdefault(t, {})[k] = float(parts[7])
        elif line.startswith('OUTPUT_HBL,'):
            parts = line.split(',')
            hbl[t] = float(parts[3])

    n_out = max(visc_az.keys()) + 1
    out = {
        name: np.zeros((n_out, nz))
        for name in ('visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat')
    }
    for t, kd in visc_az.items():
        for k, v in kd.items():
            out['visc_az'][t, k - 1] = v
    for t, kd in diff_kz_s.items():
        for k, v in kd.items():
            out['diff_kz_s'][t, k - 1] = v
    for t, kd in diff_kz_t.items():
        for k, v in kd.items():
            out['diff_kz_t'][t, k - 1] = v
    for t, kd in ghat.items():
        for k, v in kd.items():
            out['ghat'][t, k - 1] = v
    out['hbl'] = np.array([hbl[t] for t in range(n_out)])
    return out


def compare(scenario_dir: Path) -> dict:
    npz = np.load(scenario_dir / 'kpp_experiment.npz')
    nz = int(npz['depth'].shape[0])
    fortran = parse_standalone_output(scenario_dir / 'kpp_standalone_output.txt', nz)

    print(f"{scenario_dir.name}:")
    results = {}
    for name in ('visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat', 'hbl'):
        results[name] = summarize(name, fortran[name], npz[name])
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_scenario_standalone.py <scenario_output_dir> [...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        compare(Path(arg))


if __name__ == '__main__':
    main()
