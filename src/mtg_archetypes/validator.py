import json
import logging
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

from .cards import normalize_card_name


logger = logging.getLogger(__name__)

# Cache duration for Scryfall Oracle catalog
ONE_WEEK_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Used to validate card names in archetype YAML files
# Not used when classifying a deck
SCRYFALL_CATALOG_URL = "https://api.scryfall.com/catalog/card-names"
VALID_SCOPES = {"main", "side", "any"}
ALLOWED_TOP_LEVEL_KEYS = {
    "name",
    "priority",
    "category",
    "mandatory",
    "signatures",
    "min_signatures",
    "signature_groups",
    "anti_signatures",
    "colors",
}


def fetch_scryfall_card_names(
    cache_path: Path | None = None,
    max_age_seconds: float = ONE_WEEK_SECONDS,
) -> set[str]:
    """
    Download or load cached Scryfall card catalog to get all valid Oracle card names.

    If cache_path exists and is newer than max_age_seconds (default: 7 days),
    it is loaded from disk. Otherwise, a fresh catalog is downloaded and cached.

    Returns a set of normalized card names and face names.
    """
    if cache_path and cache_path.exists():
        try:
            mtime = cache_path.stat().st_mtime
            is_fresh = (time.time() - mtime) <= max_age_seconds
            if is_fresh:
                with open(cache_path, "r", encoding="utf-8") as fp:
                    names = json.load(fp)
                    if isinstance(names, list):
                        return _normalize_card_set(names)
        except Exception as e:
            logger.warning("Could not read cached Scryfall data from %s: %s", cache_path, e)

    req = urllib.request.Request(
        SCRYFALL_CATALOG_URL,
        headers={
            "User-Agent": "mtg-archetypes-validator/0.1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
        names = data.get("data", [])

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fp:
            json.dump(names, fp)

    return _normalize_card_set(names)


def _normalize_card_set(names: list[str]) -> set[str]:
    norm_set: set[str] = set()
    for name in names:
        norm = normalize_card_name(name)
        if norm:
            norm_set.add(norm)
            if " // " in norm:
                for face in norm.split(" // "):
                    f_norm = face.strip()
                    if f_norm:
                        norm_set.add(f_norm)
    return norm_set


def validate_archetype_file(
    file_path: Path,
    known_cards: set[str] | None = None,
) -> list[str]:
    """Validate a single archetype YAML file against schema and card database."""
    errors: list[str] = []
    prefix = f"{file_path.name}: "

    try:
        with open(file_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
    except Exception as e:
        return [f"{prefix}YAML parse error: {e}"]

    if not isinstance(data, dict):
        return [f"{prefix}Root of YAML must be a mapping."]

    # Check top-level keys
    for k in data:
        if k not in ALLOWED_TOP_LEVEL_KEYS:
            allowed = sorted(ALLOWED_TOP_LEVEL_KEYS)
            errors.append(f"{prefix}Unknown key '{k}'. Allowed keys: {allowed}")

    # Name
    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        errors.append(f"{prefix}'name' is required and must be a non-empty string.")

    # Priority
    priority = data.get("priority")
    if priority is None:
        errors.append(f"{prefix}'priority' is required.")
    elif not isinstance(priority, int) or priority < 0 or priority > 200:
        errors.append(f"{prefix}'priority' must be an integer between 0 and 200, got {priority}.")

    # Category
    category = data.get("category")
    if category is not None and not isinstance(category, str):
        errors.append(f"{prefix}'category' must be a string if provided.")

    def check_card_name(c_name: str, context: str) -> None:
        if not c_name or not isinstance(c_name, str) or not str(c_name).strip():
            errors.append(f"{prefix}{context}: Card name cannot be empty.")
            return
        if known_cards is not None:
            norm = normalize_card_name(str(c_name))
            if norm not in known_cards:
                errors.append(f"{prefix}{context}: Unknown card '{c_name}' not found in Scryfall.")

    # Mandatory
    mandatory = data.get("mandatory", [])
    if not isinstance(mandatory, list):
        errors.append(f"{prefix}'mandatory' must be an array.")
    else:
        for idx, item in enumerate(mandatory):
            ctx = f"mandatory[{idx}]"
            if isinstance(item, str):
                check_card_name(item, ctx)
            elif isinstance(item, dict):
                c_name = item.get("card") or item.get("name")
                if not c_name:
                    errors.append(f"{prefix}{ctx}: Missing 'card' property.")
                else:
                    check_card_name(str(c_name), ctx)

                min_val = item.get("min", item.get("count", 1))
                if not isinstance(min_val, int) or min_val < 1:
                    errors.append(f"{prefix}{ctx}: 'min' must be a positive integer >= 1.")

                if "in" in item:
                    scope = item.get("in")
                    if not isinstance(scope, str) or scope not in VALID_SCOPES:
                        errors.append(
                            f"{prefix}{ctx}: Invalid 'in' value '{scope}'. Allowed: 'main', 'side', 'any'."
                        )

                for ik in item:
                    if ik not in {"card", "name", "min", "count", "in"}:
                        errors.append(f"{prefix}{ctx}: Unknown property '{ik}'.")
            else:
                errors.append(f"{prefix}{ctx}: Must be a card string or mapping.")

    # Signatures
    signatures = data.get("signatures", [])
    if not isinstance(signatures, list):
        errors.append(f"{prefix}'signatures' must be an array.")
    else:
        for idx, item in enumerate(signatures):
            if not isinstance(item, str):
                errors.append(f"{prefix}signatures[{idx}]: Card must be a string.")
            else:
                check_card_name(item, f"signatures[{idx}]")

    min_sig = data.get("min_signatures")
    if min_sig is not None:
        if not isinstance(min_sig, int) or min_sig < 0:
            errors.append(f"{prefix}'min_signatures' must be an integer >= 0.")

    # Signature Groups
    sig_groups = data.get("signature_groups", [])
    if not isinstance(sig_groups, list):
        errors.append(f"{prefix}'signature_groups' must be an array.")
    else:
        for idx, grp in enumerate(sig_groups):
            ctx = f"signature_groups[{idx}]"
            if not isinstance(grp, dict):
                errors.append(f"{prefix}{ctx}: Must be a mapping.")
                continue

            cards = grp.get("cards", [])
            if not isinstance(cards, list) or not cards:
                errors.append(f"{prefix}{ctx}: 'cards' must be a non-empty array of card strings.")
            else:
                for c_idx, c in enumerate(cards):
                    if not isinstance(c, str):
                        errors.append(f"{prefix}{ctx}.cards[{c_idx}]: Must be a card string.")
                    else:
                        check_card_name(c, f"{ctx}.cards[{c_idx}]")

            grp_min = grp.get("min", 1)
            if not isinstance(grp_min, int) or grp_min < 1:
                errors.append(f"{prefix}{ctx}: 'min' must be a positive integer >= 1.")

            if "in" in grp:
                grp_scope = grp.get("in")
                if not isinstance(grp_scope, str) or grp_scope not in VALID_SCOPES:
                    errors.append(
                        f"{prefix}{ctx}: Invalid 'in' value '{grp_scope}'. Allowed: 'main', 'side', 'any'."
                    )

            for gk in grp:
                if gk not in {"cards", "min", "in"}:
                    errors.append(f"{prefix}{ctx}: Unknown property '{gk}'.")

    # Anti Signatures
    anti = data.get("anti_signatures", [])
    if not isinstance(anti, list):
        errors.append(f"{prefix}'anti_signatures' must be an array.")
    else:
        for idx, item in enumerate(anti):
            ctx = f"anti_signatures[{idx}]"
            if isinstance(item, str):
                check_card_name(item, ctx)
            elif isinstance(item, dict):
                c_name = item.get("card") or item.get("name")
                if not c_name:
                    errors.append(f"{prefix}{ctx}: Missing 'card' property.")
                else:
                    check_card_name(str(c_name), ctx)

                if "in" in item:
                    scope = item.get("in")
                    if not isinstance(scope, str) or scope not in VALID_SCOPES:
                        errors.append(
                            f"{prefix}{ctx}: Invalid 'in' value '{scope}'. Allowed: 'main', 'side', 'any'."
                        )

                for ak in item:
                    if ak not in {"card", "name", "in"}:
                        errors.append(f"{prefix}{ctx}: Unknown property '{ak}'.")
            else:
                errors.append(f"{prefix}{ctx}: Must be a card string or mapping.")

    return errors


def validate_rules_directory(
    archetypes_dir: Path,
    known_cards: set[str] | None = None,
) -> tuple[int, list[str]]:
    """
    Validate all format directories and YAML files under archetypes_dir.

    Returns:
        (total_files_checked, list_of_errors)
    """
    errors: list[str] = []
    total_files = 0

    if not archetypes_dir.is_dir():
        return 0, [f"Archetypes directory '{archetypes_dir}' does not exist."]

    # Disallow YAML files at the root of archetypes/
    root_yamls = list(archetypes_dir.glob("*.yaml")) + list(archetypes_dir.glob("*.yml"))
    if root_yamls:
        for f in root_yamls:
            errors.append(
                f"Invalid file location '{f.name}': YAML files must be placed in a format folder, "
                f"e.g. 'archetypes/legacy/{f.name}'."
            )

    names_by_format: dict[str, set[str]] = defaultdict(set)

    for fmt_dir in sorted(archetypes_dir.iterdir()):
        if not fmt_dir.is_dir() or fmt_dir.name.startswith("."):
            continue

        fmt_name = fmt_dir.name.lower()
        yaml_files = sorted(list(fmt_dir.glob("*.yaml")) + list(fmt_dir.glob("*.yml")))

        for yaml_path in yaml_files:
            total_files += 1
            file_errors = validate_archetype_file(yaml_path, known_cards=known_cards)
            errors.extend(file_errors)
            if file_errors:
                continue

            # Check duplicate name within format
            try:
                with open(yaml_path, "r", encoding="utf-8") as fp:
                    d = yaml.safe_load(fp)
                    arch_name = str(d.get("name", "")).strip().lower()
                    if arch_name in names_by_format[fmt_name]:
                        dupe_name = d.get("name")
                        errors.append(
                            f"{fmt_name}/{yaml_path.name}: Duplicate archetype name "
                            f"'{dupe_name}' already defined in {fmt_name}."
                        )
                    names_by_format[fmt_name].add(arch_name)
            except Exception as e:
                logger.debug(
                    "Failed to read archetype name from %s for duplicate check: %s", yaml_path, e
                )

    return total_files, errors
