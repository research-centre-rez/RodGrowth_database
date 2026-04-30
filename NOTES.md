# Zachovat jen základní názvy, '_naklon' varianty smazat:
python -m src.main --input data/raw.xlsx --output output/clean.csv --resolve-variants base

# Zachovat jen '_naklon' varianty, základní názvy smazat:
python -m src.main --input data/raw.xlsx --output output/clean.csv --resolve-variants variant

# Jen reportovat, nic nemaže (výchozí):
python -m src.main --input data/raw.xlsx --output output/clean.csv