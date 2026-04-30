"""Steps 2–3: Sort into canonical order and deduplicate shared corner overlaps."""

import logging
from typing import Final

import pandas as pd

from .config import (
    DATA_COL_KAMPAN,
    DATA_COL_PS,
    DATA_COL_SIDE,
    SIDE_ORDER,
)

logger: Final = logging.getLogger(__name__)

_SORT_COLS: Final[list[str]] = [
    DATA_COL_KAMPAN,
    DATA_COL_PS,
    DATA_COL_SIDE,
    "DD_logical",
]
_DEDUP_COLS: Final[list[str]] = [
    DATA_COL_KAMPAN,
    DATA_COL_PS,
    DATA_COL_SIDE,
    "DD_logical",
]


def sort_measurements(df: pd.DataFrame) -> pd.DataFrame:
    """Sort measurements into canonical Kampan → PS → Side → DD order.

    Side is treated as an ordered categorical (s1 < s2 < … < s6) to
    guarantee correct ordering regardless of string sort order.

    Args:
        df: Mapped DataFrame from map_and_clone().

    Returns:
        Sorted DataFrame with a reset integer index.

    Raises:
        KeyError: If any sort column is absent from the DataFrame.
    """
    missing = set(_SORT_COLS) - set(df.columns)
    if missing:
        raise KeyError(f"Sort columns missing from DataFrame: {missing}")

    df = df.copy()
    side_cat = pd.CategoricalDtype(categories=SIDE_ORDER, ordered=True)
    df[DATA_COL_SIDE] = df[DATA_COL_SIDE].astype(side_cat)

    df_sorted = df.sort_values(by=_SORT_COLS, ascending=True, na_position="last").reset_index(
        drop=True
    )

    logger.info("Sort complete: %d rows in canonical order.", len(df_sorted))
    return df_sorted


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate measurements for the same logical position.

    After cloning, a shared corner may carry two entries with slightly
    different measured values (machine traversed it twice). The first
    occurrence after sorting is kept.

    Deduplication key: [Kampan, PS, Side, DD_logical].

    Args:
        df: Sorted DataFrame from sort_measurements().

    Returns:
        DataFrame with at most one row per unique logical position.
    """
    rows_before = len(df)
    df_dedup = df.drop_duplicates(subset=_DEDUP_COLS, keep="first").reset_index(drop=True)
    removed = rows_before - len(df_dedup)

    if removed:
        logger.warning(
            "Deduplication removed %d row(s). Likely cause: machine measured shared corners twice.",
            removed,
        )
    else:
        logger.info("Deduplication: no duplicate positions found.")

    return df_dedup
