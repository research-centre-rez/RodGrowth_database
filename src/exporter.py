"""Step 4: Export clean data to CSV (JSON export prepared as opt-in)."""

import json
import logging
from pathlib import Path
from typing import Final, Literal

import pandas as pd

logger: Final = logging.getLogger(__name__)


def export(
    df: pd.DataFrame,
    output_path: str | Path,
    fmt: Literal["csv", "json"] = "csv",
) -> None:
    """Export the clean DataFrame to CSV or JSON.

    Args:
        df: Final clean DataFrame.
        output_path: Destination file path.
        fmt: Output format — 'csv' (default) or 'json' (records-oriented).

    Raises:
        ValueError: If an unsupported format is requested.
        OSError: If the output directory cannot be created or written to.
    """
    output_path = Path(output_path)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            df.to_csv(output_path, index=False, encoding="utf-8")
        elif fmt == "json":
            records = json.loads(df.to_json(orient="records", force_ascii=False))
            output_path.write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        else:
            raise ValueError(f"Unsupported export format: '{fmt}'")

    except OSError:
        logger.exception("Failed to write output to %s.", output_path)
        raise

    logger.info("Exported %d rows to %s (format: %s).", len(df), output_path, fmt)
