# Validation results

The narrative validation results for MITgcm-vs-Python-port agreement are
maintained as two standalone, per-scheme reports:

- [`KPP_port_validation/KPP_VALIDATION_RESULTS.md`](KPP_port_validation/KPP_VALIDATION_RESULTS.md)
  — the KPP boundary-layer scheme.
- [`GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`](GGL90_port_validation/GGL90_VALIDATION_RESULTS.md)
  — the GGL90 turbulence closure.

Each document is self-contained: per-experiment results, causal mechanisms
for every real discrepancy, a shared-infrastructure section written with
that scheme's own framing, and a physical/methodological limitations
section. `README.md` (this directory) keeps the three-way comparison method
description, the directory guide, and a compact per-experiment status table
pointing at both reports above.
