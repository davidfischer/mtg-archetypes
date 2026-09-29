"""Declarative YAML Archetype Classification Engine."""

import importlib.resources
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .cards import expand_card_counts
from .cards import normalize_card_name
from .cards import slugify_archetype


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CardRequirement:
    """Card requirement with copy count and board scope ('main', 'side', or 'any')."""

    card: str
    min: int = 1
    scope: str = "any"


@dataclass(frozen=True, slots=True)
class SignatureGroup:
    """Group of signature cards where at least `min` cards must be present in `scope`."""

    cards: frozenset[str]
    min: int = 1
    scope: str = "any"


@dataclass(frozen=True, slots=True)
class ArchetypeRule:
    """Parsed, immutable archetype definition rule."""

    name: str
    slug: str
    priority: int
    category: str | None
    mandatory: tuple[CardRequirement, ...]
    signatures: frozenset[str]
    min_signatures: int
    signature_groups: tuple[SignatureGroup, ...]
    anti_signatures: tuple[CardRequirement, ...]
    source_file: str | None = None


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """The result of classifying a decklist."""

    matched: bool
    name: str | None = None
    slug: str | None = None
    priority: int = 0
    category: str | None = None
    matched_rule: str | None = None


class ArchetypeClassifier:
    """Evaluates decks against declarative YAML archetype rules with deterministic priority."""

    def __init__(self, rules_dir: Path | str | None = None):
        if rules_dir:
            self.rules_dir = Path(rules_dir)
        else:
            # Check for repo-local archetypes/ directory first
            repo_root = Path(__file__).resolve().parents[2]
            local_archetypes = repo_root / "archetypes"
            if local_archetypes.is_dir():
                self.rules_dir = local_archetypes
            else:
                # Fallback to packaged archetypes via importlib.resources
                try:
                    ref = importlib.resources.files("mtg_archetypes") / "archetypes"
                    self.rules_dir = Path(str(ref))
                except Exception:
                    self.rules_dir = local_archetypes

        self._rules_by_format: dict[str, list[ArchetypeRule]] = {}
        self.load_all_rules()

    def load_all_rules(self) -> None:
        """
        Load and normalize YAML rules for each format.

        Strictly enforces 1 YAML file per archetype under archetypes/<format>/<archetype>.yaml.
        """
        self._rules_by_format.clear()
        if not self.rules_dir.exists():
            logger.warning("Rules directory %s does not exist", self.rules_dir)
            return

        # Look for subdirectories per format (e.g. archetypes/vintage, archetypes/legacy)
        for fmt_dir in sorted(self.rules_dir.iterdir()):
            if not fmt_dir.is_dir() or fmt_dir.name.startswith("."):
                continue

            fmt = fmt_dir.name.lower().strip()
            parsed_rules: list[ArchetypeRule] = []
            yaml_files = sorted(list(fmt_dir.glob("*.yaml")) + list(fmt_dir.glob("*.yml")))

            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, "r", encoding="utf-8") as fp:
                        raw = yaml.safe_load(fp)
                except Exception as e:
                    logger.error("Error reading %s: %s", yaml_file, e)
                    continue

                if not isinstance(raw, dict) or "name" not in raw:
                    logger.warning(
                        "Skipping invalid archetype file (missing 'name'): %s", yaml_file
                    )
                    continue

                rule = self._parse_rule_dict(raw, yaml_file)
                if rule:
                    parsed_rules.append(rule)

            # Sort by priority descending; tie-break by specificity (most constraints first)
            parsed_rules.sort(
                key=lambda r: (r.priority, len(r.mandatory) + len(r.signatures)),
                reverse=True,
            )
            self._rules_by_format[fmt] = parsed_rules
            logger.debug("Loaded %d archetype rules for %s", len(parsed_rules), fmt)

    def _parse_rule_dict(self, raw: dict[str, Any], source_file: Path) -> ArchetypeRule | None:
        """Parse raw YAML dictionary into normalized ArchetypeRule dataclass."""
        name = str(raw["name"]).strip()
        slug = slugify_archetype(name)
        priority = int(raw.get("priority", 50))
        category = raw.get("category")

        # Parse mandatory cards: list of str or tables { card: "...", min: 1, in: "main" }
        mandatory: list[CardRequirement] = []
        for item in raw.get("mandatory", []):
            if isinstance(item, dict):
                c_name = item.get("card") or item.get("name") or ""
                try:
                    min_cnt = int(item.get("min", item.get("count", 1)))
                except (ValueError, TypeError):
                    min_cnt = 1
                scope = item.get("in", "any")
            else:
                c_name = str(item)
                min_cnt = 1
                scope = "any"

            norm = normalize_card_name(c_name)
            if norm:
                mandatory.append(CardRequirement(card=norm, min=min_cnt, scope=scope))

        # Parse signatures (flat list)
        signatures: set[str] = set()
        for c in raw.get("signatures", []):
            if c:
                norm = normalize_card_name(str(c))
                signatures.add(norm)
                if " // " in norm:
                    signatures.add(norm.split(" // ")[0].strip())

        default_min_sig = 1 if signatures else 0
        min_sig = int(raw.get("min_signatures", default_min_sig))

        # Parse signature_groups: list of { cards: [...], min: N, in: "main" }
        signature_groups: list[SignatureGroup] = []
        for grp in raw.get("signature_groups", []):
            if not isinstance(grp, dict):
                continue
            grp_cards = set()
            for c in grp.get("cards", []):
                norm = normalize_card_name(str(c))
                if norm:
                    grp_cards.add(norm)
                    if " // " in norm:
                        grp_cards.add(norm.split(" // ")[0].strip())
            try:
                grp_min = int(grp.get("min", 1))
            except (ValueError, TypeError):
                grp_min = 1
            grp_scope = grp.get("in", "any")

            if grp_cards:
                signature_groups.append(
                    SignatureGroup(
                        cards=frozenset(grp_cards),
                        min=grp_min,
                        scope=grp_scope,
                    )
                )

        # Parse anti_signatures: list of str or { card: "...", in: "main" }
        anti_signatures: list[CardRequirement] = []
        for item in raw.get("anti_signatures", []):
            if isinstance(item, dict):
                c_name = item.get("card") or item.get("name") or ""
                scope = item.get("in", "any")
            else:
                c_name = str(item)
                scope = "any"

            norm = normalize_card_name(c_name)
            if norm:
                anti_signatures.append(CardRequirement(card=norm, min=1, scope=scope))
                if " // " in norm:
                    anti_signatures.append(
                        CardRequirement(card=norm.split(" // ")[0].strip(), min=1, scope=scope)
                    )

        return ArchetypeRule(
            name=name,
            slug=slug,
            priority=priority,
            category=category,
            mandatory=tuple(mandatory),
            signatures=frozenset(signatures),
            min_signatures=min_sig,
            signature_groups=tuple(signature_groups),
            anti_signatures=tuple(anti_signatures),
            source_file=str(source_file),
        )

    def get_rules(self, format_name: str) -> list[ArchetypeRule]:
        """Return parsed rules for the given format."""
        return self._rules_by_format.get(format_name.lower().strip(), [])

    def classify(
        self,
        mainboard_cards: Iterable[Any],
        sideboard_cards: Iterable[Any] | None = None,
        format: str = "legacy",
    ) -> ClassificationResult:
        """
        Classify deck cards into an archetype.

        Args:
            mainboard_cards: Iterable of mainboard cards (card names or dicts with card and count).
            sideboard_cards: Optional iterable of sideboard cards.
            format: Format to classify against (e.g. 'vintage', 'legacy', 'modern').

        Returns:
            ClassificationResult dataclass. If no rule matches, returns
            matched=False with name=None.
        """
        fmt = format.lower().strip()
        mb_counts = expand_card_counts(mainboard_cards)
        sb_counts = expand_card_counts(sideboard_cards or [])
        total_counts = mb_counts + sb_counts

        norm_mb = set(mb_counts.keys())
        norm_sb = set(sb_counts.keys())
        norm_total = set(total_counts.keys())

        # Helper to get card count in specified board scope
        def count_in_scope(card: str, scope: str) -> int:
            if scope == "main":
                counts = mb_counts
            elif scope == "side":
                counts = sb_counts
            else:
                counts = total_counts

            cnt = counts.get(card, 0)
            if " // " in card:
                cnt = max(cnt, counts.get(card.split(" // ")[0].strip(), 0))
            return cnt

        def card_present_in_scope(card: str, scope: str) -> bool:
            if scope == "main":
                pool = norm_mb
            elif scope == "side":
                pool = norm_sb
            else:
                pool = norm_total
            return card in pool

        # Evaluate explicit YAML rules in priority order
        rules = self._rules_by_format.get(fmt, [])

        for rule in rules:
            # Check mandatory cards: each must meet minimum quantity in its scope
            failed_mandatory = False
            for req in rule.mandatory:
                if count_in_scope(req.card, req.scope) < req.min:
                    failed_mandatory = True
                    break
            if failed_mandatory:
                continue

            # Check anti_signatures: NONE may be present in its scope
            failed_anti = False
            for anti in rule.anti_signatures:
                if card_present_in_scope(anti.card, anti.scope):
                    failed_anti = True
                    break
            if failed_anti:
                continue

            # Check signatures pool (if defined)
            if rule.signatures:
                hits = sum(1 for c in rule.signatures if c in norm_total)
                if hits < rule.min_signatures:
                    continue

            # Check signature_groups: ALL groups must meet their threshold
            failed_group = False
            for grp in rule.signature_groups:
                if grp.scope == "main":
                    pool = norm_mb
                elif grp.scope == "side":
                    pool = norm_sb
                else:
                    pool = norm_total

                grp_hits = sum(1 for c in grp.cards if c in pool)
                if grp_hits < grp.min:
                    failed_group = True
                    break

            if failed_group:
                continue

            # First matching rule in priority order wins immediately
            return ClassificationResult(
                matched=True,
                name=rule.name,
                slug=rule.slug,
                priority=rule.priority,
                category=rule.category,
                matched_rule=rule.name,
            )

        # No rule matched -> Unclassified
        return ClassificationResult(
            matched=False,
            name=None,
            slug=None,
            priority=0,
            category=None,
            matched_rule=None,
        )
