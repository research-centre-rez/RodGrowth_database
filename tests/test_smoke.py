"""Smoke tests — verify that the package imports cleanly.

These tests don't validate logic, just confirm that:
  1. All modules can be imported without errors.
  2. The schema configuration loads correctly.
  3. The CLI parser is constructable.

If any of these fail, something is fundamentally broken
(missing dependency, import cycle, syntax error, broken YAML).
"""

import os

# Ensure the test schema is loaded before importing src modules.
os.environ.setdefault("RODGROWTH_SCHEMA", "config/schema.test.yaml")


def test_config_loads() -> None:
    """Schema YAML loads and required constants are populated."""
    from src import config

    assert config.SHEET_DATA
    assert config.SHEET_KEY
    assert config.DATA_COL_KAMPAN
    assert config.DATA_COL_PS
    assert len(config.SIDE_ORDER) == 6
    assert config.EXPECTED_ROWS_PER_SAMPLE == 66


def test_all_modules_import() -> None:
    """Every src module can be imported without error."""
    from src import cleaner, exporter, main, mapper, reader, validator

    assert cleaner is not None
    assert exporter is not None
    assert main is not None
    assert mapper is not None
    assert reader is not None
    assert validator is not None


def test_cli_parser_builds() -> None:
    """CLI argument parser is constructable and exposes expected flags."""
    from src.main import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "--input",
            "dummy.xlsx",
            "--output",
            "dummy.csv",
            "--resolve-variants",
            "base",
        ]
    )

    assert args.fmt == "csv"
    assert args.resolve_variants == "base"
    assert str(args.input) == "dummy.xlsx"


def test_extract_base_ps() -> None:
    """The base PS extractor correctly strips variant suffixes."""
    from src.validator import extract_base_ps

    assert extract_base_ps("XX01") == "XX01"
    assert extract_base_ps("XX01_naklon") == "XX01"
    assert extract_base_ps("XX02_v2") == "XX02"
    assert extract_base_ps("DR03") == "DR03"
    assert extract_base_ps("  XX01  ") == "XX01"
