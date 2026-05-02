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
    DATA_COL_DD_LOGICAL,
    DATA_COL_KAMPAN,
    DATA_COL_PS,
    DATA_COL_SIDE,
    EXPECTED_ROWS_PER_SAMPLE,
    KEY_COL_DD,
    KEY_COL_SIDE,
    RESOLVABLE_SUFFIX,
    SIDE_ORDER,
)

logger: Final = logging.getLogger(__name__)


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
    """Remove one side of '_naklon' duplicate pairs from the DataFrame.

    Only PS pairs where one form is '<base>' and the other is '<base>_naklon'
    are eligible for resolution. Other suffixes (e.g. '_uxcx', '_test') are
    treated as legitimate distinct samples and left untouched, even when a
    base sibling exists in the data — those pairs are reported as variants
    but never auto-deleted.

    Args:
        df: Clean DataFrame after deduplication.
        keep: Which side of a '_naklon' pair to retain.
            'base'    -- keep 'XX01',         drop 'XX01_naklon'
            'variant' -- keep 'XX01_naklon',  drop 'XX01'

    Returns:
        DataFrame with the unwanted side of resolvable '_naklon' pairs removed.
    """
    df = df.copy()
    df["_ps_str"] = df[DATA_COL_PS].astype(str).str.strip()
    df["_base_ps"] = df[DATA_COL_PS].astype(str).map(extract_base_ps)

    # A row is a "_naklon variant" if its PS equals base + RESOLVABLE_SUFFIX.
    naklon_form = df["_base_ps"] + RESOLVABLE_SUFFIX
    df["_is_naklon"] = df["_ps_str"] == naklon_form
    df["_is_bare_base"] = df["_ps_str"] == df["_base_ps"]

    # Find bases that have BOTH a bare form AND a naklon form in the data.
    bases_with_naklon = set(df.loc[df["_is_naklon"], "_base_ps"].unique())
    bases_with_bare = set(df.loc[df["_is_bare_base"], "_base_ps"].unique())
    resolvable_bases = bases_with_naklon & bases_with_bare

    if not resolvable_bases:
        logger.info(
            "resolve_ps_variants: no '%s' pairs found, nothing removed.",
            RESOLVABLE_SUFFIX,
        )
        return df.drop(columns=["_ps_str", "_base_ps", "_is_naklon", "_is_bare_base"])

    logger.info(
        "Resolving %d '%s' pair(s): %s. Keeping: '%s'.",
        len(resolvable_bases),
        RESOLVABLE_SUFFIX,
        sorted(resolvable_bases),
        keep,
    )

    if keep == "base":
        # Drop naklon rows whose base is in resolvable set.
        mask_drop = df["_base_ps"].isin(resolvable_bases) & df["_is_naklon"]
    else:  # keep == "variant"
        # Drop bare base rows whose base is in resolvable set.
        mask_drop = df["_base_ps"].isin(resolvable_bases) & df["_is_bare_base"]

    rows_before = len(df)
    df = (
        df[~mask_drop]
        .drop(columns=["_ps_str", "_base_ps", "_is_naklon", "_is_bare_base"])
        .reset_index(drop=True)
    )

    logger.info(
        "Removed %d row(s) belonging to discarded '%s' side.",
        rows_before - len(df),
        RESOLVABLE_SUFFIX,
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
    required = {DATA_COL_KAMPAN, DATA_COL_PS, DATA_COL_SIDE, DATA_COL_DD_LOGICAL}
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
                df.loc[sample_mask, DATA_COL_DD_LOGICAL].astype(int),
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

    A 'true variant' is a PS string with a suffix that ALSO has a sibling
    PS without that suffix in the same dataset (e.g. 'XX01_naklon' alongside 'XX01').

    A PS string with a suffix but no base sibling (e.g. 'XX01_uxcx' alone)
    is treated as a unique sample, not a variant — its longer name is just
    descriptive, not a duplicate marker.

    Args:
        df: DataFrame containing the PS column.

    Returns:
        DataFrame of true-variant rows with columns
        [Kampan, PS, base_ps, base_present_in_data].
        Empty if no true variants found.
    """
    df = df.copy()
    df["base_ps"] = df[DATA_COL_PS].astype(str).map(extract_base_ps)
    df["is_suffixed"] = df[DATA_COL_PS].astype(str).str.strip() != df["base_ps"]

    # For each base, check whether ANY row has the bare base form (no suffix).
    bases_present_as_bare = set(df.loc[~df["is_suffixed"], "base_ps"].unique())

    df["base_present_in_data"] = df["base_ps"].isin(bases_present_as_bare)

    # A true variant: has a suffix AND its base exists in the data as a bare row.
    is_true_variant = df["is_suffixed"] & df["base_present_in_data"]

    variants = (
        df.loc[
            is_true_variant,
            [DATA_COL_KAMPAN, DATA_COL_PS, "base_ps"],
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    if variants.empty:
        logger.info("PS variant check: no true variant pairs found.")
    else:
        logger.warning(
            "Found %d true variant(s) — both base and suffixed form exist: %s",
            len(variants),
            variants[DATA_COL_PS].tolist(),
        )

    # Also log suffixed lone samples for awareness, but don't add them to report.
    is_suffixed_lone = df["is_suffixed"] & ~df["base_present_in_data"]
    lone_count = df.loc[is_suffixed_lone, DATA_COL_PS].nunique()
    if lone_count:
        logger.info(
            "Found %d suffixed lone sample(s) (no base sibling) — treated as unique, not variants.",
            lone_count,
        )

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
