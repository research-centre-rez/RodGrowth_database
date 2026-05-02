"""Step 1: Map raw measurements to logical positions and clone shared corners.

Two paths through the mapper:
  1. Rows WITHOUT pre-filled Side: standard inner merge against the position key.
     Ballast rows (machine coord not in key) are dropped. Shared corners are cloned.
  2. Rows WITH pre-filled Side: kept as-is, bypass the merge entirely.
     This handles datasets where someone manually translated machine coordinates
     to logical positions before processing.

The two paths are then concatenated into a single output DataFrame.
"""

import logging
from typing import Final

import pandas as pd

from .config import DATA_COL_DD, DATA_COL_DD_LOGICAL, DATA_COL_SIDE, KEY_COL_DD, KEY_COL_OUT

logger: Final = logging.getLogger(__name__)


def _split_pre_resolved(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split raw data into pre-resolved and unresolved subsets.

    A row is considered pre-resolved if its Side column is non-empty.
    These rows skip the merge — their logical positions are trusted as-is.

    Args:
        df_raw: Raw input DataFrame.

    Returns:
        Tuple (pre_resolved, unresolved). Either may be empty.
    """
    if DATA_COL_SIDE not in df_raw.columns:
        # No Side column at all — everything goes through the merge.
        return df_raw.iloc[0:0].copy(), df_raw

    side_filled = df_raw[DATA_COL_SIDE].notna() & (
        df_raw[DATA_COL_SIDE].astype(str).str.strip() != ""
    )
    pre_resolved = df_raw[side_filled].copy()
    unresolved = df_raw[~side_filled].copy()

    return pre_resolved, unresolved


def _validate_pre_resolved(df: pd.DataFrame) -> pd.DataFrame:
    """Verify that pre-resolved rows have all required logical fields.

    For pre-resolved rows the data column DATA_COL_DD already holds the
    logical wire number (1-11), not the machine coordinate. This function
    renames it to the canonical DD_logical for downstream processing.

    Rows without a usable logical number are reported and dropped.

    Args:
        df: Pre-resolved subset (rows where Side is filled).

    Returns:
        Validated DataFrame with DATA_COL_DD renamed to DD_logical.

    Raises:
        ValueError: If the data column DATA_COL_DD is missing entirely.
    """
    if df.empty:
        return df

    if DATA_COL_DD not in df.columns:
        raise ValueError(
            f"Pre-resolved rows (Side filled) must have the data column "
            f"'{DATA_COL_DD}' holding the logical wire number. Column not found."
        )

    df = df.copy()
    df[DATA_COL_DD] = pd.to_numeric(df[DATA_COL_DD], errors="coerce").astype("Int64")

    incomplete = df[df[DATA_COL_DD].isna()]
    if not incomplete.empty:
        logger.warning(
            "Dropping %d pre-resolved row(s) with missing or non-numeric '%s'.",
            len(incomplete),
            DATA_COL_DD,
        )
        df = df.dropna(subset=[DATA_COL_DD])

    df = df.rename(columns={DATA_COL_DD: DATA_COL_DD_LOGICAL})
    return df


def _merge_unresolved(df_raw: pd.DataFrame, df_key: pd.DataFrame) -> pd.DataFrame:
    """Run the standard merge for rows without pre-filled Side.

    Args:
        df_raw: Unresolved subset of raw data.
        df_key: Position key DataFrame.

    Returns:
        DataFrame with Side and DD_logical assigned from the key.
    """
    if df_raw.empty:
        return pd.DataFrame()

    if DATA_COL_DD not in df_raw.columns:
        raise KeyError(
            f"Unresolved rows (Side empty) require machine coordinate column '{DATA_COL_DD}'."
        )

    # Drop stale logical columns — key is authoritative for unresolved rows.
    stale = [c for c in (DATA_COL_SIDE, KEY_COL_DD) if c in df_raw.columns]
    if stale:
        df_raw = df_raw.drop(columns=stale)

    df_key_renamed = df_key.rename(
        columns={KEY_COL_OUT: DATA_COL_DD, KEY_COL_DD: DATA_COL_DD_LOGICAL}
    )

    df_mapped = df_raw.merge(df_key_renamed, on=DATA_COL_DD, how="inner")
    return df_mapped


def map_and_clone(df_raw: pd.DataFrame, df_key: pd.DataFrame) -> pd.DataFrame:
    """Assign logical positions to raw measurements.

    Rows with pre-filled Side bypass the merge (trusted as-is).
    Rows without Side go through the standard merge against the position key,
    which drops ballast rows and clones shared corners.

    Args:
        df_raw: Raw machine data.
        df_key: Position key with columns [OUT, Side, DD_No].

    Returns:
        DataFrame with Side and DD_logical columns. Combines both paths.

    Raises:
        ValueError: If pre-resolved rows are missing required fields.
        KeyError: If unresolved rows are missing the machine coordinate column.
    """
    rows_before = len(df_raw)

    pre_resolved, unresolved = _split_pre_resolved(df_raw)

    pre_resolved_validated = _validate_pre_resolved(pre_resolved)
    merged = _merge_unresolved(unresolved, df_key)

    df_combined = pd.concat([pre_resolved_validated, merged], ignore_index=True)

    rows_after = len(df_combined)
    logger.info(
        "Map & Clone: %d raw rows → %d mapped rows (pre-resolved: %d, merged: %d).",
        rows_before,
        rows_after,
        len(pre_resolved_validated),
        len(merged),
    )
    return df_combined
