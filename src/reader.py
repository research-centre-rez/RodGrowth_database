"""Read-only extraction from the source Excel file.

This module never writes back to Excel. openpyxl is not imported here.
All reads go through pandas, which uses openpyxl as a read-only engine.
"""

import logging
from pathlib import Path
from typing import Final

import pandas as pd

from .config import (
    DATA_COL_DD,
    DATA_COL_SIDE,
    KEY_COL_DD,
    KEY_COL_OUT,
    KEY_COL_SIDE,
    SHEET_DATA,
    SHEET_KEY,
    SIDE_ORDER,
)

logger: Final = logging.getLogger(__name__)


def _validate_side_values(series: pd.Series, context: str) -> None:
    """Check that all side values in the data match SIDE_ORDER from schema.

    Args:
        series: Series of side values to validate.
        context: Human-readable label for error messages (e.g. 'key sheet').

    Raises:
        ValueError: If any side value is not in SIDE_ORDER.
    """
    actual = set(series.dropna().astype(str).unique())
    expected = set(SIDE_ORDER)
    unknown = actual - expected
    if unknown:
        raise ValueError(
            f"{context}: found Side values not declared in schema: "
            f"{sorted(unknown)}. Expected one of: {SIDE_ORDER}. "
            f"Update structure.side_order in your schema YAML."
        )


def load_key(source_path: str | Path) -> pd.DataFrame:
    """Load the position key from the PP_key sheet.

    The key maps each machine coordinate (OUT) to one or two logical
    positions. Shared corners appear as two rows with the same OUT value.

    Args:
        source_path: Path to the Excel file containing the key sheet.

    Returns:
        DataFrame with columns [OUT, Side, DD_No], deduplicated of
        exact-duplicate rows, cast to correct dtypes.

    Raises:
        FileNotFoundError: If the Excel file does not exist.
        ValueError: If required columns are missing from the key sheet.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    try:
        df = pd.read_excel(
            source_path,
            sheet_name=SHEET_KEY,
            dtype={KEY_COL_OUT: "Int64", KEY_COL_DD: "Int64"},
        )
    except Exception:
        logger.exception("Failed to read key sheet '%s' from %s.", SHEET_KEY, source_path)
        raise

    required = {KEY_COL_OUT, KEY_COL_SIDE, KEY_COL_DD}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Key sheet is missing required columns: {missing}")

    df = (
        df[[KEY_COL_OUT, KEY_COL_SIDE, KEY_COL_DD]]
        .dropna(subset=[KEY_COL_OUT])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    # NEW: Validate that side values in the key match SIDE_ORDER from schema.
    _validate_side_values(df[KEY_COL_SIDE], context="key sheet")

    logger.info(
        "Key loaded: %d position mappings, %d unique OUT values.",
        len(df),
        df[KEY_COL_OUT].nunique(),
    )
    return df


def load_raw_data(source_path: str | Path) -> pd.DataFrame:
    """Load raw measurement data from the data sheet.

    The function tolerates rows that have already been manually translated
    (Side filled in). Rows without machine coordinate AND without Side
    are treated as malformed and dropped with a warning.

    Args:
        source_path: Path to the Excel file.

    Returns:
        Raw DataFrame with the machine coordinate column coerced to nullable int.

    Raises:
        FileNotFoundError: If the Excel file does not exist.
        ValueError: If neither the machine coordinate nor Side column exists.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    try:
        df = pd.read_excel(source_path, sheet_name=SHEET_DATA)
    except Exception:
        logger.exception("Failed to read data sheet '%s' from %s.", SHEET_DATA, source_path)
        raise

    has_machine_coord = DATA_COL_DD in df.columns
    has_side = DATA_COL_SIDE in df.columns

    if not has_machine_coord and not has_side:
        raise ValueError(
            f"Data sheet must contain at least one of: "
            f"machine coordinate column '{DATA_COL_DD}' or logical side column '{DATA_COL_SIDE}'."
        )

    if has_machine_coord:
        df[DATA_COL_DD] = pd.to_numeric(df[DATA_COL_DD], errors="coerce").astype("Int64")

    logger.info("Raw data loaded: %d rows, %d columns.", *df.shape)
    return df
