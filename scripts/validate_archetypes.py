#!/usr/bin/env python3
"""CLI script to validate all archetype YAML definitions against schema and Scryfall."""

import argparse
import sys
from pathlib import Path

from mtg_archetypes.validator import fetch_scryfall_card_names
from mtg_archetypes.validator import validate_rules_directory


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate MTG archetype YAML files.")
    parser.add_argument(
        "--archetypes-dir",
        type=Path,
        default=repo_root / "archetypes",
        help="Path to directory containing format folders of YAML rules.",
    )
    parser.add_argument(
        "--check-cards",
        action="store_true",
        help="Validate card names against Scryfall Oracle catalog.",
    )
    parser.add_argument(
        "--update-scryfall",
        action="store_true",
        help="Download/update fresh Scryfall Oracle card catalog from Scryfall API.",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=repo_root / ".cache" / "scryfall_catalog.json",
        help="Path to cached Scryfall card catalog file.",
    )

    args = parser.parse_args()

    known_cards = None
    if args.update_scryfall or args.check_cards:
        if args.update_scryfall or not args.cache_file.exists():
            print("Fetching Scryfall card catalog...")
            if args.update_scryfall and args.cache_file.exists():
                args.cache_file.unlink()
        known_cards = fetch_scryfall_card_names(cache_path=args.cache_file)
        print(f"Loaded {len(known_cards)} known Oracle cards and face names from Scryfall.")

    print(f"Validating YAML rules in {args.archetypes_dir}...")
    total_files, errors = validate_rules_directory(
        archetypes_dir=args.archetypes_dir,
        known_cards=known_cards,
    )

    print(f"Checked {total_files} archetype YAML files.")
    if errors:
        print(f"\nFound {len(errors)} validation error(s):\n", file=sys.stderr)
        for err in errors:
            print(f"  ❌ {err}", file=sys.stderr)
        return 1

    print("✅ All archetype files are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
