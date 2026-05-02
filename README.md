# RodGrowth Database Pipeline (DRPP)

A modular backend pipeline that cleans and validates experimental measurement
data from hexagonal sample-growth campaigns. It reads a raw machine Excel
export, maps machine coordinates to logical positions on the hexagonal
construction (6 sides × 11 wires = 66 wires per sample), resolves shared
corners, deduplicates overlapping measurements, and produces clean CSV or
JSON output ready for downstream visualization (e.g. Vue.js + Apache ECharts).

The pipeline is **read-only** with respect to the source Excel file — output
is always written to a separate file in the desired format. Schema-specific
terminology (sheet names, column names, side identifiers) is held in YAML
configuration files, so the same code runs against multiple datasets without
modification.

---

## Features

- **Read-only Excel access.** Source files are never overwritten. pandas with
  the openpyxl read engine handles all input.
- **Vectorized mapping & shared-corner cloning.** A single pandas inner merge
  against the position key drops ballast rows, maps logical positions, and
  clones shared corners — no row-by-row iteration.
- **Pre-resolved row support.** Rows where someone has already manually filled
  in the logical side (e.g. a colleague translated coordinates by hand) bypass
  the merge and are trusted as-is. Rows without manual translation go through
  the standard key lookup.
- **Defensive validation.** Every clean run produces validation reports:
  - `incomplete_samples.csv` — samples missing wire positions, with the exact
    list of missing `face/PP` slots.
  - `ps_variants.csv` — pattern-sample pairs where both a base name and a
    suffixed variant (e.g. `XX01` and `XX01_naklon`) appear in the data.
- **Targeted variant resolution.** Optional auto-deletion of `_naklon` pairs.
  Other suffixes (e.g. `_uxcx`) are reported but never auto-deleted, since
  they typically represent legitimate distinct experiments.
- **YAML schema configuration.** Two configs (`schema.test.yaml`,
  `schema.prod.yaml`) hold all dataset-specific names. Switching between
  test data and production data is a single CLI flag.
- **PowerShell task runner.** A `run.ps1` script wraps common workflows
  (install, run, test, lint, clean) with parameter validation.
- **Profissional Python project layout.** `pyproject.toml` defines the
  package, dependencies, console scripts (`rodgrowth-process`), ruff and
  pytest configuration. Editable install via `pip install -e ".[dev]"`.

---

## Prerequisites

- Python 3.10 or higher
- Git
- A working PowerShell (Windows PowerShell 5.1 or PowerShell 7) — required
  for the `run.ps1` task runner
- Conda (Miniconda or Anaconda) recommended for environment management

---

## Installation

Clone the repository and enter the project root:

```powershell
git clone <repository_url>
cd RodGrowth_database
```

Create and activate a Python environment:

```powershell
conda create -n rodgrowth python=3.11
conda activate rodgrowth
```

Install the project in editable mode with development dependencies:

```powershell
.\run.ps1 install
```

This runs `pip install -e ".[dev]"` under the hood, pulling in pandas,
openpyxl, pyyaml, plus dev tools (pytest, ruff, types-PyYAML).

If PowerShell refuses to run the script because of execution policy,
allow user-scoped scripts once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Usage

All everyday workflows go through `run.ps1`. Show the available tasks:

```powershell
.\run.ps1 help
```

### Run the pipeline

Default run uses the test schema and the default input path:

```powershell
.\run.ps1 run
```

With explicit parameters:

```powershell
.\run.ps1 run -Schema prod `
              -InputFile "C:\path\to\Database.xlsx" `
              -OutputFile "output\clean.csv" `
              -Reports "output\reports" `
              -Format csv `
              -Variants none
```

### Parameters

| Parameter      | Values                       | Default                              |
| -------------- | ---------------------------- | ------------------------------------ |
| `-Schema`      | `test`, `prod`               | `test`                               |
| `-InputFile`   | path to source Excel         | `data\raw_machine_output.xlsx`       |
| `-OutputFile`  | output file path             | `output\clean.csv`                   |
| `-Reports`     | directory for CSV reports    | `output\reports`                     |
| `-Format`      | `csv`, `json`                | `csv`                                |
| `-Variants`    | `none`, `base`, `variant`    | `none`                               |

### Variant resolution modes

The `-Variants` flag controls how `_naklon` pairs are handled. Only the
exact `_naklon` suffix is auto-resolved; other suffixes are reported but
never auto-deleted.

- `none` (default) — report only, no rows removed.
- `base` — when both `XX01` and `XX01_naklon` exist, drop `XX01_naklon`,
  keep `XX01`.
- `variant` — when both exist, drop `XX01`, keep `XX01_naklon`.

Recommended workflow: run with `none` first, inspect
`output\reports\ps_variants.csv` to see what would be affected, then re-run
with the desired resolution.

### Other tasks

```powershell
.\run.ps1 test     # run pytest
.\run.ps1 lint     # run ruff against src/ and tests/
.\run.ps1 clean    # remove output and cache directories
```

---

## Schema configuration

All dataset-specific names live in YAML files under `config/`:

- `config\schema.test.yaml` — fictional names used for development and CI.
  Committed to Git.
- `config\schema.prod.yaml` — real internal names. **Listed in `.gitignore`,
  never committed.**

Schema structure (test version):

```yaml
sheets:
  data: RustDD_Data
  key: DD_key

key_columns:
  side: Side
  dd_no: DD_No
  out: OUT

data_columns:
  kampan: Kampan
  ps: PS
  side: Side
  dd: DD
  dd_logical: DD_logical

structure:
  side_order: [s1, s2, s3, s4, s5, s6]
  dd_min: 1
  dd_max: 11
```

The `data_columns.dd` column plays a dual role: in unresolved rows it holds
the raw machine coordinate, while in pre-resolved rows it holds the logical
wire number (1–11). The pipeline distinguishes the two cases by whether
`Side` is filled in.

`structure.side_order` defines the canonical sorting order for sides and
must contain exactly six entries. The values must match the side
identifiers actually used in the data.

To onboard a new dataset, copy `schema.test.yaml` to `schema.prod.yaml` and
fill in the real sheet names, column headers, and side identifiers. No code
changes are needed.

---

## Pipeline flow

```
┌────────────────┐
│ Excel source   │  read-only, never overwritten
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ reader         │  load key + raw data, validate side values
└───────┬────────┘
        │
        ▼
┌──────────────────────────────────┐
│ mapper                           │
│   • split rows by Side filled?   │
│   • pre-resolved → trust as-is   │
│   • unresolved   → merge on key  │
│   • concat both paths            │
└───────┬──────────────────────────┘
        │
        ▼
┌────────────────┐
│ cleaner        │  sort canonically, deduplicate
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ validator      │  optional _naklon resolution + reports
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ exporter       │  CSV or JSON output
└────────────────┘
```

---

## Project structure

```text
.
├── config/
│   ├── schema.test.yaml         # committed — fictional names
│   └── schema.prod.yaml         # gitignored — real internal names
├── src/
│   ├── __init__.py
│   ├── config.py                # YAML schema loader + constants
│   ├── reader.py                # Excel read (read-only)
│   ├── mapper.py                # Step 1: map & clone
│   ├── cleaner.py               # Steps 2–3: sort & deduplicate
│   ├── validator.py             # Validation reports + variant resolution
│   ├── exporter.py              # Step 4: CSV/JSON output
│   └── main.py                  # CLI entry point
├── tests/
│   ├── __init__.py
│   └── test_smoke.py            # smoke tests (imports, parser, helpers)
├── data/                        # local datasets (git-ignored)
├── output/                      # generated outputs (git-ignored)
├── .github/workflows/ci.yml     # CI: ruff + pytest
├── .gitignore
├── LICENSE
├── pyproject.toml               # package, dependencies, tool config
├── run.ps1                      # PowerShell task runner
└── README.md
```

---

## Testing and linting

CI runs ruff and pytest against every push and pull request. Run them
locally before pushing:

```powershell
.\run.ps1 lint     # ruff check src/ tests/
.\run.ps1 test     # pytest tests/
```

Configuration for both tools lives in `pyproject.toml` under
`[tool.ruff]` and `[tool.pytest.ini_options]`.

---

## Validation reports

After every run, the directory specified by `-Reports` may contain:

- **`incomplete_samples.csv`** — samples whose row count differs from the
  expected 66. Columns: `Kampan`, `PS`, `row_count`, `expected`, `delta`,
  `missing_positions` (e.g. `s3/3, s3/4, s5/7`).
- **`ps_variants.csv`** — pattern samples where both a base name and a
  suffixed variant exist. The auto-resolver only acts on `_naklon` pairs;
  other suffixes are listed for human review.

If a run is fully clean (all samples complete, no variant pairs), no
report files are written.

---

## Versioning and contribution

- Feature branches use the `feature/<name>` prefix; bug fixes use
  `bugfix/<name>`.
- All changes go through pull requests; CI must be green before merge.
- Release versions are tagged as `v<major>.<minor>.<patch>` (semver).
- Code follows the Google Python Style Guide; docstrings are in English.
- Use the `logging` module — never `print` — for runtime output.

---

## License

Proprietary. Copyright © 2026 Centrum výzkumu Řež, s. r. o. All rights reserved.
For internal use only. See `LICENSE` for details.
