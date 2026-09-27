# Rebuilds the local Pyrfume ingredient cache used by fragrance retrieval.
# Downloads the configured datasets filters materials and writes data/pyrfume_catalog.json.
# This should be run to regenerate the catalog file when new datasets are added.

from __future__ import annotations

import sys
from pathlib import Path

# Put the backend package root on sys.path so src imports resolve when run as a script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Settings
from src.services.pyrfume_catalog import build_catalog, save_catalog_cache


def main() -> None:
    settings = Settings()
    # Default path is backend/data/pyrfume_catalog.json unless overridden in settings.
    cache_path = Path(settings.pyrfume_catalog_cache_path)
    # Build from GoodScents Leffingwell and IFRA then save the filtered ingredient list.
    records = build_catalog(settings.pyrfume_datasets)
    save_catalog_cache(records, cache_path)
    print(f"Saved {len(records)} ingredients to {cache_path}")


if __name__ == "__main__":
    main()
