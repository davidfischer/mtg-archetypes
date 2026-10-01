#!/usr/bin/env python3
"""
Classify MTGO decks using mtg-archetypes and report coverage.

Running:

    git clone https://github.com/davidfischer/modometa-mtgo-data.git ../modometa-mtgo-data
    python scripts/classify_mtgo_decks.py --data-dir ../modometa-mtgo
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from collections import defaultdict
from pathlib import Path
from typing import Any

from mtg_archetypes import ArchetypeClassifier
from mtg_archetypes.engine import ArchetypeRule


KNOWN_FORMATS: set[str] = {
    "modern",
    "legacy",
    "vintage",
    "pauper",
    "premodern",
    "pioneer",
    "standard",
}

EXCLUDED_KEYWORDS: tuple[str, ...] = (
    "commander",
    "contraption",
    "limited",
    "draft",
    "sealed",
    "cube",
)


def detect_format(tournament: dict[str, Any], filename: str) -> str | None:
    """Detect MTG competitive format from tournament JSON or filename, excluding Commander."""
    fmt_raw = tournament.get("Formats")
    if fmt_raw:
        fmt_clean = str(fmt_raw).strip().lower()
        if fmt_clean in KNOWN_FORMATS:
            return fmt_clean
        return None

    # Fallback to name or filename matching if Formats field is missing or None
    name_and_file = f"{tournament.get('Name', '')} {filename}".lower()
    if any(k in name_and_file for k in EXCLUDED_KEYWORDS):
        return None

    for kf in KNOWN_FORMATS:
        if re.search(r"\b" + re.escape(kf) + r"\b", name_and_file):
            return kf

    return None


def parse_args() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    repo_root = Path(__file__).resolve().parents[1]
    default_data_dir = repo_root.parent / "modometa-mtgo-data"
    default_archetypes_dir = repo_root / "archetypes"

    parser = argparse.ArgumentParser(description="Classify MTGO decks and report rule coverage.")
    parser.add_argument(
        "--data-dir",
        "-d",
        type=Path,
        default=default_data_dir,
        help=f"Path to modometa-mtgo-data repository (default: {default_data_dir}).",
    )
    parser.add_argument(
        "--archetypes-dir",
        type=Path,
        default=default_archetypes_dir,
        help=f"Path to archetypes rules directory (default: {default_archetypes_dir}).",
    )
    parser.add_argument(
        "--formats",
        "-f",
        nargs="+",
        help="Specific formats to evaluate (e.g. modern legacy). Defaults to all supported formats.",
    )
    parser.add_argument(
        "--show-archetype-counts",
        action="store_true",
        help="Show match count for each archetype rule per format.",
    )
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = parse_args()
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}", file=sys.stderr)
        return 1

    tournaments_dir = data_dir / "Tournaments" / "MTGO"
    if not tournaments_dir.exists():
        if (data_dir / "MTGO").exists():
            tournaments_dir = data_dir / "MTGO"
        else:
            tournaments_dir = data_dir

    archetypes_dir = args.archetypes_dir.resolve()
    classifier = ArchetypeClassifier(rules_dir=archetypes_dir)

    all_formats = sorted(classifier._rules_by_format.keys())
    if args.formats:
        target_formats = [f.lower().strip() for f in args.formats]
    else:
        target_formats = all_formats

    t_start = time.time()
    total_decks_by_fmt: Counter[str] = Counter()
    matched_decks_by_fmt: Counter[str] = Counter()
    rule_counts_by_fmt: dict[str, Counter[str]] = defaultdict(Counter)

    scanned_files = 0
    for fpath in tournaments_dir.rglob("*.json"):
        scanned_files += 1
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (json.JSONDecodeError, OSError):  # noqa: S112
            continue

        tournament = data.get("Tournament", {})
        fmt = detect_format(tournament, str(fpath))
        if not fmt or fmt not in target_formats:
            continue

        decks = data.get("Decks", [])
        if not decks:
            continue

        for deck in decks:
            total_decks_by_fmt[fmt] += 1
            mainboard = deck.get("Mainboard", [])
            sideboard = deck.get("Sideboard", [])
            result = classifier.classify(mainboard, sideboard, format=fmt)
            if result.matched and result.matched_rule:
                matched_decks_by_fmt[fmt] += 1
                rule_counts_by_fmt[fmt][result.matched_rule] += 1

    t_elapsed = time.time() - t_start

    # Check for rules matching 0 decks
    zero_match_rules: list[ArchetypeRule] = []
    total_rules = 0

    for fmt in target_formats:
        rules = classifier.get_rules(fmt)
        total_rules += len(rules)
        counts = rule_counts_by_fmt[fmt]
        for r in rules:
            if counts[r.name] == 0:
                zero_match_rules.append(r)

    # Print summary report
    print("=" * 80)
    print("mtg-archetypes MTGO Classification Report")
    print("=" * 80)
    print(f"Data directory:       {data_dir}")
    print(f"Tournaments scanned:  {scanned_files:,} JSON files")
    print(f"Execution time:       {t_elapsed:.2f} seconds")
    print()

    print(
        f"{'Format':<14} {'Rules':>6} {'Total Decks':>13} {'Classified':>12} {'Unclassified':>14} {'Coverage':>10}"
    )
    print("-" * 80)

    total_decks = 0
    total_matched = 0

    for fmt in target_formats:
        rules = classifier.get_rules(fmt)
        tot = total_decks_by_fmt[fmt]
        mat = matched_decks_by_fmt[fmt]
        unclass = tot - mat
        pct = (mat / tot * 100) if tot else 0.0
        rule_cnt = len(rules)

        total_decks += tot
        total_matched += mat

        print(
            f"{fmt.capitalize():<14} {rule_cnt:>6} {tot:>13,} {mat:>12,} {unclass:>14,} {pct:>9.2f}%"
        )

    print("-" * 80)
    total_pct = (total_matched / total_decks * 100) if total_decks else 0.0
    print(
        f"{'Total':<14} {total_rules:>6} {total_decks:>13,} {total_matched:>12,} "
        f"{total_decks - total_matched:>14,} {total_pct:>9.2f}%"
    )
    print("=" * 80)
    print()

    # Zero-match rules
    print("Rules Matching 0 Decks:")
    print("-" * 80)
    if not zero_match_rules:
        print(f"✓ All {total_rules} rules across evaluated formats matched at least 1 deck!")
    else:
        print(f"⚠ Found {len(zero_match_rules)} rule(s) with 0 matches:")
        for r in zero_match_rules:
            src = r.source_file or "unknown"
            try:
                rel_src = Path(src).relative_to(repo_root)
            except ValueError:
                rel_src = src
            print(f"  • {r.name} (Priority {r.priority}) -> {rel_src}")

    # Archetype counts per format
    if args.show_archetype_counts:
        print()
        print("Archetype Match Counts:")
        print("-" * 80)
        for fmt in target_formats:
            rules = classifier.get_rules(fmt)
            if not rules:
                continue
            print(f"\n{fmt.capitalize()} ({len(rules)} rules):")
            counts = [(r.name, rule_counts_by_fmt[fmt][r.name]) for r in rules]
            counts.sort(key=lambda x: (-x[1], x[0]))
            for name, count in counts:
                print(f"  {name:<30} {count:>8,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
