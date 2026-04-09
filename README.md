# RodGrowth_database

A modular backend pipeline designed for automated research data processing, database maintenance, and data cleaning. This system is built to process Excel datasets (specifically `RustPP_Data`), resolve missing physical coordinates, and eliminate duplicate pattern sample variants, preparing the data for further interactive visualization and organizational GUI integration.

## Features

* **Automated Coordinate Resolution:** Identifies and fills missing `Face` and wire number (`PP`) values based on a provided mapping key. Utilizes dynamic anchor tracking (lookbehind/lookahead) and consecutive streak counting for precise assignments.
* **Variant Removal:** Automatically detects and removes rows containing variant Pattern Samples (PS) based on base string extraction, operating from bottom to top to preserve correct row indexing.
* **Format Preservation:** Uses `openpyxl` to perform in-place modifications, ensuring that the original Excel formatting, styling, and unrelated data remain strictly untouched.
* **Organizational Standards Compliance:** Fully compliant with internal standards, including strict PEP8 formatting enforced by Flake8, comprehensive testing via `pytest`, and automated CI/CD checks via GitHub Actions.

## Prerequisites

* Python 3.10 or higher
* Git
* Docker (for containerized execution, as per internal standards)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_name>
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

The pipeline is executed via the command-line interface. 

**Important:** Ensure that the target Excel files are fully closed in your spreadsheet editor before running the script to prevent `PermissionError`.

```bash
python -m src.main --input "path/to/input.xlsx" --output "path/to/output.xlsx" --key "path/to/key.xlsx"
```

If the input, output, and key data are all contained within the same file (e.g., in a `data` folder), provide the identical path for all arguments:

```bash
python -m src.main --input "data/dataset.xlsx" --output "data/dataset.xlsx" --key "data/dataset.xlsx"
```

## Testing and Linting

This project enforces strict quality gates. Before creating a Pull Request, ensure all tests and linter checks pass locally.

To run the test suite:
```bash
pytest
```

To check for PEP8 compliance and cyclomatic complexity limits:
```bash
flake8 src tests --count --select=E9,F63,F7,F82,C901,E203 --show-source --statistics
```

## Project Structure

```text
.
├── src/
│   ├── __init__.py
│   ├── db_processor.py      # Core logic for coordinate resolution
│   ├── duplicate_finder.py  # Logic for identifying and removing PS variants
│   └── main.py              # CLI entry point and pipeline orchestration
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py
├── data/                    # Directory for local datasets (git-ignored)
├── .github/workflows/       # CI/CD configurations
├── .gitignore
├── requirements.txt
└── README.md
```

## Versioning and Contribution

All contributors must adhere to the internal organizational standards described in `versioning.md` and `templates.md`. 
* Use proper branching strategies (`feature/`, `bugfix/`).
* Submit Pull Requests for code reviews.
* Ensure Git tags are used for release versions.
* All code must utilize English docstrings following the Google Python Style Guide.
* Use the standard logging module instead of print statements.
