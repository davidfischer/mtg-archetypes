"""CLI interface for mtg-archetypes."""

import argparse
import json
import sys
from pathlib import Path

from .cards import parse_decklist_text
from .engine import ArchetypeClassifier


def main(args: list[str] | None = None) -> int:
    """Run mtg-archetypes CLI."""
    parser = argparse.ArgumentParser(
        prog="mtg-archetypes",
        description="A fast MTG deck archetype classifier for common formats.",
    )
    parser.add_argument(
        "format",
        help=(
            "Format to classify against (e.g. legacy, vintage, modern, "
            "pioneer, pauper, standard, premodern)."
        ),
    )
    parser.add_argument(
        "deck_file",
        nargs="?",
        type=Path,
        default=None,
        help="Path to decklist file (reads from stdin if omitted).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose details (e.g. priority, category, or 'Unclassified').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON.",
    )
    parser.add_argument(
        "--rules-dir",
        type=Path,
        default=None,
        help="Custom directory containing archetype definitions.",
    )

    parsed_args = parser.parse_args(args)

    # Read deck text from file or stdin
    if parsed_args.deck_file:
        if not parsed_args.deck_file.exists():
            sys.stderr.write(f"Error: Deck file '{parsed_args.deck_file}' does not exist.\n")
            return 1
        raw_text = parsed_args.deck_file.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.stderr.write("\nError: No decklist provided via file argument or piped stdin.\n")
            return 1
        raw_text = sys.stdin.read()

    mainboard, sideboard = parse_decklist_text(raw_text)
    if not mainboard:
        sys.stderr.write("Error: Decklist contains no valid mainboard cards.\n")
        return 1

    classifier = ArchetypeClassifier(rules_dir=parsed_args.rules_dir)
    result = classifier.classify(
        mainboard_cards=mainboard,
        sideboard_cards=sideboard,
        format=parsed_args.format,
    )

    if parsed_args.json:
        data = {
            "matched": result.matched,
            "name": result.name,
            "slug": result.slug,
            "priority": result.priority,
            "category": result.category,
            "matched_rule": result.matched_rule,
        }
        print(json.dumps(data, indent=2))
    elif parsed_args.verbose:
        if result.matched:
            print(f"Archetype: {result.name}")
            print(f"Priority:  {result.priority}")
            if result.category:
                print(f"Category:  {result.category}")
        else:
            print("Archetype: Unclassified")
    else:
        # Default Unix behavior: output archetype name on match, nothing at all on no match
        if result.matched:
            print(result.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
