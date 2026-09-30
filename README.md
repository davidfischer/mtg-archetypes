# mtg-archetypes

Magic: The Gathering deck archetype classifier

```bash
cat ur-delver.txt | mtg-archetypes legacy
# Izzet Delver
```

---

## Overview

`mtg-archetypes` is a rule-based deck archetype classifier for MTG across competitive formats (Legacy, Vintage, Modern, Pioneer, Pauper, Premodern, Standard).

- **Declarative**: One YAML file per archetype with archetype defining card constraints
- **Board scope awareness**: Enforce cards in mainboard (`in: "main"`), sideboard (`in: "side"`), or anywhere in the 75
- **Exact card quantities**: Enforce minimum copy counts (e.g. `min: 3` *Mishra's Workshop* -> "Shops")
- **Multi-group signature logic**: Require combinations across multiple card pools (`signature_groups`)
- **Deterministic**: A deck either matches a defined archetype or goes unclassified
- **CLI & Library**: Use the standalone command line tool or use it as a Python module

---

## Installation

```bash
pip install mtg-archetypes
```

Or if you have [`uv`](https://docs.astral.sh/uv/) installed, you can use mtg-archetypes directly:

```bash
cat ur-delver.txt | uvx mtg-archetypes legacy
```

---

## Quickstart

### CLI Usage

Pipe any decklist directly into `mtg-archetypes`:

```bash
cat delver.txt | mtg-archetypes legacy
# Izzet Delver
```

Or pass a file argument:

```bash
mtg-archetypes vintage jewel_shops.txt
# Jewel Shops
```

#### Silent on No Match

When a deck does not match any rules in the format, the CLI outputs **nothing at all**:

```bash
echo "60 Plains" | mtg-archetypes legacy
# (outputs nothing, exit code 0)
```

#### Verbose Output (`--verbose`)

Pass `--verbose` to inspect priorities, categories, or see `"Archetype: Unclassified"`:

```bash
cat delver.txt | mtg-archetypes legacy --verbose
```
```text
Archetype: Izzet Delver
Priority:  100
Category:  Tempo
```

```bash
echo "60 Plains" | mtg-archetypes legacy --verbose
```
```text
Archetype: Unclassified
```

#### JSON Output (`--json`)

```bash
cat delver.txt | mtg-archetypes legacy --json
```

```json
{
  "matched": true,
  "name": "Izzet Delver",
  "slug": "izzet-delver",
  "priority": 100,
  "category": "Tempo",
  "matched_rule": "Izzet Delver"
}
```

If unclassified:

```json
{
  "matched": false,
  "name": null,
  "slug": null,
  "priority": 0,
  "category": null,
  "matched_rule": null
}
```

---

## Python Library Usage

```python
from mtg_archetypes import ArchetypeClassifier

classifier = ArchetypeClassifier()

# Or use:
# decklist = "4 Delver of Secrets\n..."
# mtg_archetypes.parse_decklist_text(decklist)
mainboard = [
    "4 Delver of Secrets",
    "4 Daze",
    "4 Force of Will",
    "4 Lightning Bolt",
    "4 Volcanic Island",
    "4 Brainstorm",
]
sideboard = [
    "2 Pyroblast",
    "1 Meltdown",
    "2 Grafdigger's Cage",
]

result = classifier.classify(mainboard, sideboard, format="legacy")

if result.matched:
    print(f"Archetype: {result.name} (Priority {result.priority})")
else:
    print("Unclassified deck")
```

---

## Archetype YAML Schema

Each archetype is defined in its own file under `archetypes/<format>/<slug>.yaml`.

### Example: Vintage Jewel Shops

```yaml
# archetypes/vintage/jewel-shops.yaml
name: "Jewel Shops"
category: "Shops"
priority: 95
min_signatures: 2

# At least 3 Mishra's Workshop copies required in mainboard
# At least one Coveted Jewel
mandatory:
  - card: "Mishra's Workshop"
    min: 3
    in: "main"
  - card: "Coveted Jewel"
    in: "main"

signatures:
  - "Tinker"
  - "Trinisphere"
  - "The One Ring"
  - "Phyrexian Metamorph"

anti_signatures:
  # Sphere of Resistance can be in sideboard, but not mainboard!
  # Otherwise, it is "Sphere Shops"
  - card: "Sphere of Resistance"
    in: "main"
  - "Doomsday"
```

### Example: Vintage CounterVine

Demonstrating multi-group condition logic (`signature_groups`):

```yaml
# archetypes/vintage/countervine.yaml
name: "CounterVine"
category: "Aggro"
priority: 85

mandatory:
  - card: "Bazaar of Baghdad"
    min: 3
    in: "main"

# Multiple signature pools evaluated with AND logic
signature_groups:
  - min: 1
    in: "main"
    cards:
      - "Master of Death"
      - "Squee, Goblin Nabob"
  - min: 2
    in: "main"
    cards:
      - "Basking Rootwalla"
      - "Blazing Rootwalla"
```

### Priority System & Conventions

- **Priority >= 50**: Specific variants should have higher priority than their broader counterparts (eg. Red Prison vs Red Stompy).
- **Priority < 50**: Broad "fallback" or "good stuff" archetypes (e.g. generic *Control*, *Midrange*, or *Stompy* catch-alls). Also, decks like *Stoneblade* may be here so they don't match more specific archetypes like *Death & Taxes*.
- The highest priority archetype where all the "mandatory", "signature_groups", and none of the "anti_signature" rules match will be selected. In the event a deck matches two archetypes of equal priority, the archetype with more rules be selected.

### Supported Directives

| Directive | Description |
| :--- | :--- |
| `name` | **Required**. Display name of the archetype. |
| `priority` | **Required**. Integer (0-200) for tie-breaking when a deck matches multiple candidate rules. Higher wins. |
| `category` | *Optional*. Format specific strategy categorization (e.g. `"Tempo"`, `"Combo"`, `"Aggro"`, `"Control"`). |
| `mandatory` | *Optional*. List of cards that **must** be present. Accepts card strings or mappings: `{ card: "...", min: N, in: "main" \| "side" \| "any" }`. |
| `signatures` | *Optional*. List of signature cards evaluated against `min_signatures`. |
| `min_signatures` | *Optional*. Minimum count of signature cards required to match (defaults to 1). |
| `signature_groups` | *Optional*. List of group mappings `{ cards: [...], min: N, in: "main" \| "side" \| "any" }`. All groups must pass. |
| `anti_signatures` | *Optional*. Cards that disqualify the deck if present. Accepts card strings or mappings: `{ card: "...", in: "main" \| "side" \| "any" }`. |

---

## Validation & Card Name Checking

The repository includes a validation script that verifies all YAML files against the schema and can optionally validate card names against the official Scryfall card catalog:

```bash
# Validate YAML syntax, required fields, and rules schema
uv run python scripts/validate_archetypes.py

# Also validate every card name against Scryfall catalog
uv run python scripts/validate_archetypes.py --check-cards
```

---

## Development & Testing

```bash
# Run test suite
uv run pytest

# Run linter and formatter
uv run ruff check .
uv run ruff format --check .

# Always check all archetype files before submitting a PR
uv run python scripts/validate_archetypes.py --check-cards
```

---

## Acknowledgments & Prior Art

This project was heavily inspired by [Badaro/MTGOFormatData](https://github.com/Badaro/MTGOFormatData).
