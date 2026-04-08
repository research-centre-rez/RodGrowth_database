import argparse
import logging
import pandas as pd
from pathlib import Path
import sys

from db_processor import build_coordinate_map, process_rust_data_safely
from duplicate_finder import highlight_ps_variants

# Nastavení logování podle standardů
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point for the Rust data processing pipeline.

    Parses command-line arguments, loads the configuration key, processes
    the raw coordinate data to fill missing sides, and finally identifies
    and highlights duplicate/variant pattern samples.
    """
    parser = argparse.ArgumentParser(
        description="Process and validate Rust measurement data."
    )
    parser.add_argument(
        "--input", type=str, required=True, help="Path to the input Excel file."
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path where the processed Excel file will be saved.",
    )
    parser.add_argument(
        "--key",
        type=str,
        required=True,
        help="Path to the Excel file containing the 'DD_key' mapping sheet.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    key_path = Path(args.key)

    if not input_path.exists():
        logger.error("Input file does not exist: %s", input_path)
        sys.exit(1)

    if not key_path.exists():
        logger.error("Key file does not exist: %s", key_path)
        sys.exit(1)

    logger.info("Starting data processing pipeline...")

    # Krok 1: Načtení mapovacího klíče
    try:
        logger.info("Loading key map from %s", key_path)
        key_df = pd.read_excel(key_path, sheet_name="DD_key")
        coord_map = build_coordinate_map(key_df)
    except Exception as e:
        logger.error("Failed to load and build coordinate map: %s", e)
        sys.exit(1)

    # Krok 2: Doplnění chybějících stran
    try:
        logger.info("Processing coordinates and fixing missing sides...")
        process_rust_data_safely(str(input_path), str(output_path), coord_map)
    except Exception as e:
        logger.error("Error during coordinate processing: %s", e)
        sys.exit(1)

    # Krok 3: Vyhledání a obarvení duplicit
    try:
        logger.info("Scanning for PS duplicates and variants...")
        highlight_ps_variants(str(output_path), str(output_path))
    except Exception as e:
        logger.error("Error during duplicate highlighting: %s", e)
        sys.exit(1)

    logger.info("Pipeline finished successfully. Output saved to: %s", output_path)


if __name__ == "__main__":
    main()
