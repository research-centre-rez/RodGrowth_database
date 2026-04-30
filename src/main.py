"""Orchestration entry point for the PS measurement processing pipeline."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Final

from .cleaner import deduplicate, sort_measurements
from .exporter import export
from .mapper import map_and_clone
from .reader import load_key, load_raw_data
from .validator import resolve_ps_variants, run_validation

logger: Final = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="PS measurement data cleaning pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the raw machine Excel file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the cleaned output CSV file.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("output/reports"),
        help="Directory for validation report CSVs.",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        dest="fmt",
        help="Output format.",
    )
    parser.add_argument(
        "--resolve-variants",
        choices=["none", "base", "variant"],
        default="none",
        dest="resolve_variants",
        help=(
            "How to handle PS duplicate pairs (e.g. 'XX01' vs 'XX01_naklon'). "
            "'base' keeps the plain name and drops the suffixed variant. "
            "'variant' keeps the suffixed form. 'none' only reports."
        ),
    )
    return parser


def run_pipeline(
    input_path: Path,
    output_path: Path,
    report_dir: Path,
    fmt: str,
    resolve_variants: str,
) -> None:
    """Execute the full cleaning pipeline.

    Args:
        input_path: Path to the source Excel file.
        output_path: Destination path for cleaned data.
        report_dir: Directory for validation report CSVs.
        fmt: Export format ('csv' or 'json').
        resolve_variants: How to resolve PS variant pairs ('none', 'base', 'variant').
    """
    logger.info("=== Pipeline START | input=%s ===", input_path)

    try:
        df_key = load_key(input_path)
        df_raw = load_raw_data(input_path)
    except (FileNotFoundError, ValueError):
        logger.exception("Failed during data loading.")
        sys.exit(1)

    try:
        df_mapped = map_and_clone(df_raw, df_key)
        df_sorted = sort_measurements(df_mapped)
        df_clean = deduplicate(df_sorted)

        if resolve_variants != "none":
            df_clean = resolve_ps_variants(df_clean, keep=resolve_variants)
    except (KeyError, ValueError):
        logger.exception("Failed during data transformation.")
        sys.exit(1)

    run_validation(df_clean, df_key, report_dir)

    try:
        export(df_clean, output_path, fmt=fmt)
    except (OSError, ValueError):
        logger.exception("Failed during export.")
        sys.exit(1)

    logger.info("=== Pipeline END | output=%s ===", output_path)


def main() -> None:
    """Parse CLI arguments and launch the pipeline."""
    args = build_parser().parse_args()

    if not args.input.exists():
        logger.error("Input file does not exist: %s", args.input)
        sys.exit(1)

    run_pipeline(
        input_path=args.input,
        output_path=args.output,
        report_dir=args.report_dir,
        fmt=args.fmt,
        resolve_variants=args.resolve_variants,
    )


if __name__ == "__main__":
    main()
