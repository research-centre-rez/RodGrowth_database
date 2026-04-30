"""Data validation: completeness checks and PS variant detection.

Replaces the openpyxl-based duplicate_finder. All findings are written
to a plain CSV report — no Excel writes, no cell coloring.
"""

import logging
import re
from pathlib import Path
from typing import Final, Literal

import pandas as pd

from .config import (
    DATA_COL_KAMPAN,
    DATA_COL_PS,
    DATA_COL_SIDE,
    EXPECTED_ROWS_PER_SAMPLE,
    KEY_COL_DD,
    KEY_COL_SIDE,
    SIDE_ORDER,
)

logger: Final = logging.getLogger(__name__)

# Column name for logical wire number (assigned by mapper.py from the key).
_LOGICAL_DD_COL: Final[str] = "DD_logical"


def extract_base_ps(ps_name: str) -> str:
    """Extract the canonical base identifier from a raw PS string.

    Strips trailing variant suffixes (underscores, descriptive text),
    retaining only the leading letter+digit core (e.g. 'XX01').

    Args:
        ps_name: Raw pattern sample string from the data sheet.

    Returns:
        Extracted base string, or the stripped original if no match.
    """
    ps_str = str(ps_name).strip()
    match = re.match(r"^([a-zA-Z]+\d+)", ps_str)
    return match.group(1) if match else ps_str


def _format_missing_positions(missing: set[tuple[str, int]]) -> str:
    """Format a set of (Side, DD_logical) tuples as a sorted display string.

    Sorting respects the canonical Side order (s1 < s2 < … < s6) and
    numeric DD ordering within each side.

    Args:
        missing: Set of (Side, DD_logical) tuples representing absent positions.

    Returns:
        Comma-separated string like 's3/3, s3/4, s5/7' (empty if input empty).
    """
    if not missing:
        return ""
    side_index = {s: i for i, s in enumerate(SIDE_ORDER)}
    ordered = sorted(missing, key=lambda x: (side_index.get(x[0], 99), x[1]))
    return ", ".join(f"{side}/{dd}" for side, dd in ordered)


def resolve_ps_variants(
    df: pd.DataFrame,
    keep: Literal["base", "variant"] = "base",
) -> pd.DataFrame:
    """Remove one side of PS duplicate pairs from the DataFrame.

    For every group where both a base PS (e.g. 'XX01') and a variant
    (e.g. 'XX01_naklon') exist, this function drops the unwanted side.
    Groups where only a base or only a variant exists are left untouched.

    Args:
        df: Clean DataFrame after deduplication.
        keep: Which side to retain.
            'base'    -- keep 'XX01',        drop 'XX01_naklon'
            'variant' -- keep 'XX01_naklon', drop 'XX01'

    Returns:
        DataFrame with the unwanted PS variants removed.
    """
    df = df.copy()
    df["_base_ps"] = df[DATA_COL_PS].astype(str).map(extract_base_ps)
    df["_is_variant"] = df[DATA_COL_PS].astype(str).str.strip() != df["_base_ps"]

    counts = df.groupby("_base_ps")["_is_variant"].nunique()
    ambiguous_bases = set(counts[counts > 1].index)

    if not ambiguous_bases:
        logger.info("resolve_ps_variants: no conflicting pairs found, nothing removed.")
        return df.drop(columns=["_base_ps", "_is_variant"])

    logger.info(
        "Resolving %d conflicting PS group(s): %s. Keeping: '%s'.",
        len(ambiguous_bases),
        sorted(ambiguous_bases),
        keep,
    )

    if keep == "base":
        mask_drop = df["_base_ps"].isin(ambiguous_bases) & df["_is_variant"]
    else:
        mask_drop = df["_base_ps"].isin(ambiguous_bases) & ~df["_is_variant"]

    rows_before = len(df)
    df = df[~mask_drop].drop(columns=["_base_ps", "_is_variant"]).reset_index(drop=True)

    logger.info(
        "Removed %d row(s) belonging to the discarded PS variant(s).",
        rows_before - len(df),
    )
    return df


def check_sample_completeness(
    df: pd.DataFrame,
    df_key: pd.DataFrame,
) -> pd.DataFrame:
    """Check that every (Kampan, PS) sample has the full set of expected positions.

    For each sample, computes:
        - actual row count
        - delta against expected (66 by default)
        - the explicit list of missing logical positions

    The set of expected positions is derived from the position key
    (every (Side, DD_No) row), so this function correctly reflects
    the project's physical structure even if SIDE_ORDER or DD ranges
    change later.

    Args:
        df: Clean deduplicated DataFrame containing Side and DD_logical columns.
        df_key: Position key DataFrame with [Side, DD_No, OUT] columns.

    Returns:
        DataFrame of incomplete samples with columns
        [Kampan, PS, row_count, expected, delta, missing_positions].
        Empty if all samples are complete.

    Raises:
        KeyError: If required columns are missing from df.
    """
    required = {DATA_COL_KAMPAN, DATA_COL_PS, DATA_COL_SIDE, _LOGICAL_DD_COL}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise KeyError(f"Cannot check completeness — missing columns: {missing_cols}")

    expected_positions: set[tuple[str, int]] = set(
        zip(df_key[KEY_COL_SIDE].astype(str), df_key[KEY_COL_DD].astype(int), strict=True)
    )

    counts = (
        df.groupby([DATA_COL_KAMPAN, DATA_COL_PS], observed=True)
        .size()
        .reset_index(name="row_count")
    )
    counts["expected"] = EXPECTED_ROWS_PER_SAMPLE
    counts["delta"] = counts["row_count"] - counts["expected"]

    incomplete = counts[counts["delta"] != 0].copy().reset_index(drop=True)

    if incomplete.empty:
        logger.info(
            "Completeness check passed: all samples have %d rows.",
            EXPECTED_ROWS_PER_SAMPLE,
        )
        incomplete["missing_positions"] = pd.Series(dtype="object")
        return incomplete

    missing_lists: list[str] = []
    for _, row in incomplete.iterrows():
        sample_mask = (df[DATA_COL_KAMPAN] == row[DATA_COL_KAMPAN]) & (
            df[DATA_COL_PS] == row[DATA_COL_PS]
        )
        present_positions: set[tuple[str, int]] = set(
            zip(
                df.loc[sample_mask, DATA_COL_SIDE].astype(str),
                df.loc[sample_mask, _LOGICAL_DD_COL].astype(int),
                strict=True,
            )
        )
        missing_positions = expected_positions - present_positions
        formatted = _format_missing_positions(missing_positions)
        missing_lists.append(formatted)

        logger.warning(
            "Sample %s / %s: %d rows (expected %d, delta %+d). Missing: %s",
            row[DATA_COL_KAMPAN],
            row[DATA_COL_PS],
            row["row_count"],
            EXPECTED_ROWS_PER_SAMPLE,
            row["delta"],
            formatted or "<none — sample has surplus rows>",
        )

    incomplete["missing_positions"] = missing_lists
    return incomplete


def find_ps_variants(df: pd.DataFrame) -> pd.DataFrame:
    """Identify PS values that are variants of a base name.

    Groups all PS strings by their extracted base. Any string longer than
    its base is flagged as a variant (e.g. 'XX01_rerun' vs 'XX01').

    Args:
        df: DataFrame containing the PS column.

    Returns:
        DataFrame of variant rows with columns [Kampan, PS, base_ps].
        Empty if no variants found.
    """
    df = df.copy()
    df["base_ps"] = df[DATA_COL_PS].astype(str).map(extract_base_ps)
    df["is_variant"] = df[DATA_COL_PS].astype(str).str.strip() != df["base_ps"]

    variants = df[df["is_variant"]][[DATA_COL_KAMPAN, DATA_COL_PS, "base_ps"]].copy()
    variants = variants.drop_duplicates().reset_index(drop=True)

    if variants.empty:
        logger.info("PS variant check: no variants found.")
    else:
        logger.warning("Found %d unique PS variant(s).", len(variants))

    return variants


def run_validation(
    df: pd.DataFrame,
    df_key: pd.DataFrame,
    report_dir: str | Path,
) -> None:
    """Run all validation checks and write findings to CSV reports.

    Args:
        df: Final clean DataFrame after deduplication.
        df_key: Position key DataFrame (needed for completeness checks).
        report_dir: Directory where validation CSVs will be written.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    incomplete = check_sample_completeness(df, df_key)
    if not incomplete.empty:
        path = report_dir / "incomplete_samples.csv"
        incomplete.to_csv(path, index=False)
        logger.info("Incompleteness report written to %s.", path)

    variants = find_ps_variants(df)
    if not variants.empty:
        path = report_dir / "ps_variants.csv"
        variants.to_csv(path, index=False)
        logger.info("PS variant report written to %s.", path)

    if incomplete.empty and variants.empty:
        logger.info("Validation clean — no reports generated.")
