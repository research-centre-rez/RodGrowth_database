"""Global configuration loaded from a YAML schema file.

The schema file (config/schema.<env>.yaml) defines all dataset-specific
names — sheets, columns, side identifiers — separately from the code.
This allows running the same pipeline against different datasets
(test, production) by switching the RODGROWTH_SCHEMA env var.

Selection is environment-driven:
    RODGROWTH_SCHEMA=config/schema.test.yaml   (default)
    RODGROWTH_SCHEMA=config/schema.prod.yaml   (production data)
"""

import logging
import os
from pathlib import Path
from typing import Final

import yaml

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH: Final[str] = "config/schema.test.yaml"


def _load_schema() -> dict:
    """Load and parse the schema YAML file.

    The schema file path is read from the RODGROWTH_SCHEMA environment
    variable. If unset, falls back to the default test schema.

    Returns:
        Parsed schema dictionary.

    Raises:
        FileNotFoundError: If the schema file does not exist.
        yaml.YAMLError: If the schema file is malformed.
        KeyError: If required schema keys are missing.
    """
    schema_env = os.environ.get("RODGROWTH_SCHEMA", _DEFAULT_SCHEMA_PATH)
    schema_path = Path(schema_env)

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema file not found: {schema_path}. "
            f"Set RODGROWTH_SCHEMA env var or create the default file."
        )

    with schema_path.open(encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    _validate_schema(schema, schema_path)
    logger.info("Loaded schema from %s", schema_path)
    return schema


def _validate_schema(schema: dict, schema_path: Path) -> None:
    """Verify that all required keys exist in the loaded schema.

    Args:
        schema: Parsed schema dictionary.
        schema_path: Path to the schema file (for error messages).

    Raises:
        KeyError: If any required key is missing.
        ValueError: If side_order does not contain exactly 6 entries.
    """
    required = {
        "sheets": ["data", "key"],
        "key_columns": ["side", "dd_no", "out"],
        "data_columns": ["kampan", "ps", "side", "dd"],
        "structure": ["side_order", "dd_min", "dd_max"],
    }

    for section, keys in required.items():
        if section not in schema:
            raise KeyError(f"Schema {schema_path} missing section: '{section}'")
        for key in keys:
            if key not in schema[section]:
                raise KeyError(f"Schema {schema_path} missing key: '{section}.{key}'")

    side_order = schema["structure"]["side_order"]
    if not isinstance(side_order, list) or len(side_order) != 6:
        raise ValueError(
            f"Schema {schema_path}: 'structure.side_order' must be a list "
            f"of exactly 6 entries (got {len(side_order)})."
        )


_SCHEMA: Final[dict] = _load_schema()

# --- Sheet names ---
SHEET_DATA: Final[str] = _SCHEMA["sheets"]["data"]
SHEET_KEY: Final[str] = _SCHEMA["sheets"]["key"]

# --- Key sheet columns ---
KEY_COL_SIDE: Final[str] = _SCHEMA["key_columns"]["side"]
KEY_COL_DD: Final[str] = _SCHEMA["key_columns"]["dd_no"]
KEY_COL_OUT: Final[str] = _SCHEMA["key_columns"]["out"]

# --- Data sheet columns ---
DATA_COL_KAMPAN: Final[str] = _SCHEMA["data_columns"]["kampan"]
DATA_COL_PS: Final[str] = _SCHEMA["data_columns"]["ps"]
DATA_COL_SIDE: Final[str] = _SCHEMA["data_columns"]["side"]
DATA_COL_DD: Final[str] = _SCHEMA["data_columns"]["dd"]

# --- Logical structure ---
SIDE_ORDER: Final[list[str]] = [str(s) for s in _SCHEMA["structure"]["side_order"]]
DD_MIN: Final[int] = int(_SCHEMA["structure"]["dd_min"])
DD_MAX: Final[int] = int(_SCHEMA["structure"]["dd_max"])
EXPECTED_ROWS_PER_SAMPLE: Final[int] = len(SIDE_ORDER) * (DD_MAX - DD_MIN + 1)
