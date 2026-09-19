# Architect Brief — Step 4: Repository Reorganization

**Repo root** = `1D_Mixing_Model/` (this is the git repo; confirmed via `git rev-parse`).
**Git handling**: use `git mv` for all in-repo moves. Do NOT commit or push — Arch commits at end after Richard passes and PO gives go-ahead.
**Overarching goal**: clean, well-organized repo a newcomer can navigate, run scenarios, and extend. Do not touch the Python *code* structure of the packages (`main/`, `GGL90_ML/GGL90_PY/`, `KPP_ML/KPP_PY/`) — imports across the codebase depend on `main.*`, `GGL90_ML.GGL90_PY.*`, `KPP_ML.KPP_PY.*`. Only move docs/tests/scripts and fix the moved files.

---

## Target layout

```
1D_Mixing_Model/
├── README.md              (REWRITE — GitHub landing page)
├── user_guide.md          (NEW — end-to-end usage guide)
├── conftest.py            (NEW — puts repo root on sys.path for pytest)
├── __init__.py            (keep)
├── main/                  (keep code; its test_*.py move to tests/)
├── GGL90_ML/GGL90_PY/     (keep; test_baseline_refactor.py moves to tests/)
├── KPP_ML/KPP_PY/         (keep; test_phase3_refactor.py moves to tests/)
├── configuration_yamls/   (keep)
├── simulations/scenarios/ (keep)
├── output/  visualizations/ (keep)
├── docs/
│   ├── GGL90/     (5 report .md + GGL90_Report.tex + GGL90_package_description.tex)
│   ├── KPP/       (MITgcm_KPP_Report.md + KPP_Report.tex + 1D_ML_draft.tex + KPP_package_description.tex)
│   └── dev_notes/ (6 misc .md + the stray C file)
├── tests/         (all 10 tests, imports fixed)
└── scripts/
    ├── analysis/            (compute_alpha_min.py, diagnose_oscillation_threshold.py, diagnose_tke_oscillations.py)
    └── scenario_generation/ (generate_training_data.py — ported to current API)
```

---

## Step 4a — DOCS (git mv; low risk, no LaTeX figure refs)

**→ docs/GGL90/**
- `GGL90_ML/GGL90_REPORT/00_GGL90_COMPREHENSIVE_REPORT.md`
- `GGL90_ML/GGL90_REPORT/01_SOURCE_CODE_SUMMARY.md`
- `GGL90_ML/GGL90_REPORT/02_ECCOV4_R4_CONFIGURATION.md`
- `GGL90_ML/GGL90_REPORT/03_QUICK_REFERENCE.md`
- `GGL90_ML/GGL90_REPORT/05_PYTHON_IMPLEMENTATION_NOTES.md`
- `GGL90_ML/GGL90_REPORT/GGL90_Report.tex`
- `GGL90_ML/GGL90_package_description.tex`

**→ docs/KPP/**
- `KPP_ML/KPP_REPORT/MITgcm_KPP_Report.md`
- `KPP_ML/KPP_REPORT/KPP_Report.tex`
- `KPP_ML/KPP_REPORT/1D_ML_draft.tex`
- `KPP_ML/KPP_package_description.tex`

**→ docs/dev_notes/**
- `GGL90_ML/GGL90_PY/IMPLEMENTATION_NOTES.md`
- `KPP_ML/KPP_PHYSICS_EXPLANATION.md`
- `KPP_ML/IMPORT_FIX_SUMMARY.md`
- `MITGCM_STAGGERING.md`
- `MIXING_SCHEMES_REPORT_README.md`
- `PHASE4_FULL_SCENARIO_VALIDATION_REPORT.md`
- `GGL90_ML/GGL90_REPORT/ECCO_GGL90_report`  → **FLAG in review**: this is 42KB of C source misfiled as a "report". Park it in dev_notes for now; Arch will confirm final home with PO.

After moving, remove the now-empty `GGL90_ML/GGL90_REPORT/` and `KPP_ML/KPP_REPORT/` dirs.
**Constraint**: `GGL90_package_description.tex` and `00_GGL90_COMPREHENSIVE_REPORT.md` have uncommitted working-tree edits (α-minimum section). `git mv` preserves them — do NOT revert or rewrite their content.

---

## Step 4b — TESTS → tests/ (HIGH RISK: import rewrites required)

Move all 10 tests via `git mv`, then fix each. **6 use relative imports that WILL break.**

| File (current) | Move to | Required fix |
|---|---|---|
| `test_alpha_comparison.py` | tests/ | `PKG_DIR = Path(__file__).resolve().parent` → `.parent.parent` |
| `test_mixing_length_methods.py` | tests/ | same `.parent`→`.parent.parent` fix |
| `main/test_ggl90_parameters.py` | tests/ | none (uses `.parent.parent`=root, absolute imports) ✓ |
| `main/test_full_scenario_validation.py` | tests/ | none (uses `.parent.parent`=root, `from main import`) ✓ |
| `main/test_staggering.py` | tests/ | none (uses `.parent.parent`=root, absolute) ✓ |
| `main/test_cross_scheme_validation.py` | tests/ | `from .physics_basis`→`from main.physics_basis`; `from .eos`→`from main.eos`; ensure repo root on sys.path (conftest covers it) |
| `main/test_physics_basis.py` | tests/ | `from physics_basis import`→`from main.physics_basis import` |
| `main/test_potential_density_gradient.py` | tests/ | `from .eos`→`from main.eos`; `from .physics_basis`→`from main.physics_basis` |
| `GGL90_ML/GGL90_PY/test_baseline_refactor.py` | tests/ | `from .ggl90_parameters`→`from GGL90_ML.GGL90_PY.ggl90_parameters`; `from .ggl90_core_driver`→`from GGL90_ML.GGL90_PY.ggl90_core_driver` |
| `KPP_ML/KPP_PY/test_phase3_refactor.py` | tests/ | `from .kpp_parameters`→`from KPP_ML.KPP_PY.kpp_parameters`; `from .kpp_core_driver`→`from KPP_ML.KPP_PY.kpp_core_driver` |

**Add `conftest.py` at repo root**:
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```
This makes `import main`, `import GGL90_ML.GGL90_PY`, `import KPP_ML.KPP_PY` resolve for every test under pytest. Relative imports still MUST be rewritten (conftest does not fix those).

**Rule for the "no fix" tests**: verify, don't assume — after moving, confirm each still resolves. If any of them has an internal relative import I missed, convert it to absolute the same way.
**Also check**: any test that reads a data/reference file by relative path (e.g. a baseline JSON) — if found, make the path absolute or move the data file alongside. Flag if encountered.

**Verification (Bob, before handoff)**: run `python -m pytest tests/ -x -q` (or run each test module). Every test that passed before the move must still pass. Report the before/after pass counts in REVIEW-REQUEST.

---

## Step 4c — SCRIPTS → scripts/

**→ scripts/analysis/** (git mv, then fix path depth):
- `compute_alpha_min.py`, `diagnose_oscillation_threshold.py`, `diagnose_tke_oscillations.py`
- Each has `PKG_DIR = Path(__file__).resolve().parent` (root today). After moving 2 levels deep, change to `PKG_DIR = Path(__file__).resolve().parents[2]`. Their SCENARIO_DIR/CONFIG_DIR/visualizations paths derive from PKG_DIR, so they resolve once PKG_DIR points at repo root. `compute_alpha_min.py` also sets `os.environ["KPP_PHYSICAL_PARAMETERS_YAML"]` from CONFIG_DIR — verify it still points into `configuration_yamls/`.
- Smoke-test at least one (e.g. `python scripts/analysis/diagnose_oscillation_threshold.py`) to confirm it finds scenarios/configs.

**→ scripts/scenario_generation/** (`generate_training_data.py`):
- Source is OUTSIDE the repo: `../generate_training_data.py` (in `1D_Mixing_Experiments/`). **Copy** it in (cannot `git mv` across repo boundary), then `git add`. Leave the original in the parent untouched (Arch will note it to PO).
- **Port its imports/API to the current package** (PO-approved):
  - `sys.path.insert(0, str(Path(__file__).parent.parent))` → insert repo root (`.parents[2]` from scripts/scenario_generation/).
  - `from KPP_PY.config import KPPConfig` → current KPP API. Read `KPP_ML/KPP_PY/` to map: config→`KPPParameters` (from `kpp_parameters`), driver→`KPPDriver` (from `kpp_core_driver`). Study `main/run_scenarios.py` / `main/run_experiment_example.py` for how KPP is actually driven now.
  - `shared_yaml/physical_parameters.yaml` → `configuration_yamls/physical_parameters.yaml`.
  - Goal: script imports cleanly and its `--help`/argparse runs without ImportError. Full end-to-end data generation may need MITgcm input files that aren't present — getting it import-clean + runnable to the arg-parse stage is the bar; note any runtime data dependency it needs.

---

## Step 4d — README.md (rewrite) + user_guide.md (new)

Write AFTER 4a–4c so paths/links are correct. Read `main/run_scenarios.py`, `main/run_experiment_example.py`, `main/config_manager.py`, and the `simulations/scenarios/scenario_*_*.yaml` files first — describe the ACTUAL interface, not assumptions.

**README.md** (concise GitHub landing): one-paragraph what-it-is (1-D ocean vertical-mixing column model: Python ports of MITgcm KPP + GGL90, scenario-driven); key features; repo map (the new tree); 3-line quick start; pointer to `user_guide.md` and `docs/`; requirements (conda env `ecco`, numpy/matplotlib/pyyaml/xarray). No emojis.

**user_guide.md** (complete, end-to-end):
1. Install / environment (conda `ecco`, deps).
2. Repo layout tour.
3. Running the built-in scenarios — exact commands for `run_scenarios.py` and `run_experiment_example.py`, all real CLI flags (`--scheme`, `--ggl90-yaml`, `--ivdc-kappa`, etc. — verify against argparse), where output/plots land.
4. Choosing a mixing scheme — KPP vs GGL90, how to select, key params (incl. GGL90 `alpha`; you may reference the docs/GGL90 α-minimum section).
5. Setting up initial conditions — structure of `scenario_*_initial_conditions.yaml` (T/S profiles, grid).
6. Setting up atmospheric forcing — `scenario_*_atmospheric_forcing.yaml` (wind stress, heat, freshwater).
7. Time integration config — `scenario_*_time_integration.yaml` (dt, duration, output freq).
8. **Adding your own experiment** — step-by-step: copy the 3 scenario yamls with a new `scenario_<name>_` prefix, edit them, run it. Concrete worked example.
9. Running tests (`pytest tests/`) and analysis scripts (`scripts/analysis/`).

---

## Git state nuance (READ FIRST)
Working tree is NOT clean. `git mv` only works on **tracked** files. Current state:
- **Tracked + modified** (edits ride along on move — do not revert): `GGL90_ML/GGL90_package_description.tex`, `GGL90_ML/GGL90_REPORT/00_GGL90_COMPREHENSIVE_REPORT.md`, `test_alpha_comparison.py`.
- **Untracked** (use plain `mv` + `git add`, NOT `git mv`): `compute_alpha_min.py`, `diagnose_oscillation_threshold.py`, `diagnose_tke_oscillations.py`.
- Ignore stray `__pycache__/*.pyc`.

## Build order
4a docs → 4b tests (+conftest, verify pytest) → 4c scripts (fix paths, smoke-test) → 4d README + user_guide. Do not reorder: docs write depends on final layout.

## When done
Write `handoff/REVIEW-REQUEST.md` listing: every file moved (from→to), every code edit made (file + what changed + why), before/after pytest pass counts, smoke-test results for scripts, and any FLAGS (the C file, any missed relative import, any runtime data dependency). List the exact files Richard should read. Do NOT commit.
