"""Step 1: Map raw measurements to logical positions and clone shared corners.

Core logic: a single pandas inner merge against the position key.
- Ballast rows (OUT not in key) are silently dropped by the inner join.
- Shared corner rows (OUT appears twice in key) are automatically cloned
  into two records, each with distinct Side/DD_No values from the key.
No explicit row iteration is used.
"""

import logging
from typing import Final

import pandas as pd

from .config import DATA_COL_DD, DATA_COL_SIDE, KEY_COL_DD, KEY_COL_OUT

logger: Final = logging.getLogger(__name__)


def map_and_clone(df_raw: pd.DataFrame, df_key: pd.DataFrame) -> pd.DataFrame:
    """Merge raw data against the position key to assign logical positions.

    Drops stale Side/DD columns from raw data before the merge so that
    the key is the single source of truth for those fields.

    Args:
        df_raw: Raw machine data. Must contain the DD column (machine coord).
        df_key: Position key with columns [OUT, Side, DD_No].

    Returns:
        DataFrame with authoritative Side and DD_No columns, retaining all
        measurement columns from df_raw. Row count may exceed df_raw if
        shared corners were cloned.

    Raises:
        KeyError: If the machine coordinate column is absent from df_raw.
    """
    if DATA_COL_DD not in df_raw.columns:
        raise KeyError(f"Machine coordinate column '{DATA_COL_DD}' not found in raw data.")

    rows_before = len(df_raw)

    # Drop stale logical columns — key is authoritative.
    stale = [c for c in (DATA_COL_SIDE, KEY_COL_DD) if c in df_raw.columns]
    if stale:
        logger.debug("Dropping pre-existing columns from raw data: %s", stale)
        df_raw = df_raw.drop(columns=stale)

    # Rename key's DD_No to a temp name to avoid collision with raw DD column.
    df_key_renamed = df_key.rename(columns={KEY_COL_OUT: DATA_COL_DD, KEY_COL_DD: "logical_DD"})

    df_mapped = df_raw.merge(df_key_renamed, on=DATA_COL_DD, how="inner")

    # Promote logical_DD to be the canonical DD column.
    df_mapped = df_mapped.rename(columns={"logical_DD": "DD_logical"})

    rows_after = len(df_mapped)
    logger.info(
        "Map & Clone: %d raw rows → %d mapped rows (delta: %+d). "
        "Ballast dropped, shared corners cloned.",
        rows_before,
        rows_after,
        rows_after - rows_before,
    )
    return df_mapped
