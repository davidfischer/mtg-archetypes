"""Card name normalization, count expansion, and decklist text parsing."""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from typing import Any


def normalize_card_name(name: str) -> str:
    """
    Normalize card names for deterministic matching.

    Strips diacritics, punctuation, extra whitespace, and converts to lowercase.
    Splits double-faced cards to front face if needed.
    """
    if not name:
        return ""
    # Normalize unicode (decompose accents)
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    # Normalize curly apostrophes / quotes
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    # Replace slashes in split cards (e.g. 'Fire // Ice' -> 'fire // ice')
    s = re.sub(r"\s*//\s*", " // ", s)
    # Remove unwanted punctuation except hyphen and slash
    s = re.sub(r"[^\w\s\-/]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def expand_card_counts(cards: Iterable[Any]) -> Counter[str]:
    """
    Extract card quantities and expand names to include full names and face names.

    Accepts an iterable of:
    - dict: {"card": str, "count": int}, {"name": str, "count": int},
            or MTGO format {"CardName": str, "Count": int}
    - tuple: (str, int)
    - str: "4 Lightning Bolt", "4x Lightning Bolt", or "Lightning Bolt"

    Returns:
        Counter mapping normalized full and face card names to their total copy count.
    """
    counts: Counter[str] = Counter()
    for item in cards:
        if not item:
            continue
        if isinstance(item, dict):
            c_name = (
                item.get("card")
                or item.get("name")
                or item.get("CardName")
                or item.get("card_name")
                or ""
            )
            raw_count = item.get("count")
            if raw_count is None:
                raw_count = item.get("Count", 1)
            try:
                c_count = int(raw_count)
            except (ValueError, TypeError):
                c_count = 1
        elif isinstance(item, tuple) and len(item) == 2:
            c_name = item[0]
            try:
                c_count = int(item[1])
            except (ValueError, TypeError):
                c_count = 1
        elif isinstance(item, str):
            m = re.match(r"^(\d+)x?\s+(.*)$", item.strip())
            if m:
                c_count = int(m.group(1))
                c_name = m.group(2)
            else:
                c_count = 1
                c_name = item
        else:
            c_name = str(item)
            c_count = 1

        norm = normalize_card_name(c_name)
        if norm:
            counts[norm] += c_count
            if " // " in norm:
                for face in norm.split(" // "):
                    face_norm = face.strip()
                    if face_norm:
                        counts[face_norm] += c_count

    return counts


def slugify_archetype(name: str) -> str:
    """Convert archetype name to clean URL slug."""
    s = name.lower().strip()
    s = re.sub(r"[/\\]", "-", s)
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def parse_decklist_text(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse standard MTG decklist text into mainboard and sideboard card dicts.

    Supports MTGO, MTG Arena, Moxfield, and MTGGoldfish formats.
    Recognizes 'Sideboard', '// Sideboard', 'SB: ...', or blank line transitions.
    """
    mainboard: list[dict[str, Any]] = []
    sideboard: list[dict[str, Any]] = []
    in_sideboard = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Check section header
        lower = line.lower()
        if lower in {"sideboard", "sideboard:", "// sideboard", "//sideboard", "# sideboard"}:
            in_sideboard = True
            continue
        if lower in {"mainboard", "mainboard:", "// mainboard", "deck", "// deck"}:
            in_sideboard = False
            continue

        # Check SB: prefix (common in some export formats)
        is_sb_line = in_sideboard
        if line.startswith("SB:") or line.startswith("sb:"):
            is_sb_line = True
            line = line[3:].strip()

        # Parse quantity and card name (e.g. "4 Lightning Bolt", "3x Brainstorm", "Force of Will")
        m = re.match(r"^(\d+)x?\s+(.*)$", line)
        if m:
            count = int(m.group(1))
            card_name = m.group(2).strip()
        else:
            count = 1
            card_name = line

        # Strip set/collector codes if present, e.g. "4 Lightning Bolt (LEA) 161" or "[LEA:161]"
        card_name = re.sub(r"\s*\([A-Za-z0-9_]+\)\s*[A-Za-z0-9_-]*$", "", card_name)
        card_name = re.sub(r"\s*\[[A-Za-z0-9_:]+\]$", "", card_name)
        card_name = card_name.strip()

        if card_name:
            entry = {"card": card_name, "count": count}
            if is_sb_line:
                sideboard.append(entry)
            else:
                mainboard.append(entry)

    return mainboard, sideboard
