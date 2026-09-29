import json
import os
import time
import urllib.request

import pytest

from mtg_archetypes.validator import fetch_scryfall_card_names
from mtg_archetypes.validator import validate_archetype_file
from mtg_archetypes.validator import validate_rules_directory


def test_valid_file_passes(tmp_path):
    f = tmp_path / "valid.yaml"
    f.write_text(
        """
name: "Test Deck"
priority: 80
category: "Combo"

mandatory:
  - card: "Lotus Petal"
    min: 2
    in: "main"
  - "Dark Ritual"

signatures:
  - "Tendrils of Agony"
min_signatures: 1

anti_signatures:
  - card: "Force of Will"
    in: "side"
""",
        encoding="utf-8",
    )
    errors = validate_archetype_file(f)
    assert errors == []


def test_invalid_keys_fail(tmp_path):
    f = tmp_path / "invalid.yaml"
    f.write_text(
        """
name: "Bad Deck"
priority: 80
invalid_key: "should fail"
""",
        encoding="utf-8",
    )
    errors = validate_archetype_file(f)
    assert any("Unknown key 'invalid_key'" in e for e in errors)


def test_missing_name_fails(tmp_path):
    f = tmp_path / "noname.yaml"
    f.write_text(
        """
priority: 50
""",
        encoding="utf-8",
    )
    errors = validate_archetype_file(f)
    assert any("'name' is required" in e for e in errors)


def test_invalid_priority_fails(tmp_path):
    f = tmp_path / "badpriority.yaml"
    f.write_text(
        """
name: "Bad Priority"
priority: 999
""",
        encoding="utf-8",
    )
    errors = validate_archetype_file(f)
    assert any("'priority' must be an integer between 0 and 200" in e for e in errors)


def test_invalid_scope_fails(tmp_path):
    f = tmp_path / "badscope.yaml"
    f.write_text(
        """
name: "Bad Scope"
priority: 50
mandatory:
  - card: "Lightning Bolt"
    in: "graveyard"
""",
        encoding="utf-8",
    )
    errors = validate_archetype_file(f)
    assert any("Invalid 'in' value 'graveyard'" in e for e in errors)


def test_duplicate_name_within_format_fails(tmp_path):
    fmt_dir = tmp_path / "legacy"
    fmt_dir.mkdir()
    (fmt_dir / "deck1.yaml").write_text("name: Duplicate\npriority: 50\n", encoding="utf-8")
    (fmt_dir / "deck2.yaml").write_text("name: Duplicate\npriority: 60\n", encoding="utf-8")

    total, errors = validate_rules_directory(tmp_path)
    assert total == 2
    assert any("Duplicate archetype name 'Duplicate'" in e for e in errors)


def test_scryfall_card_check_fails_on_typo(tmp_path):
    f = tmp_path / "typo.yaml"
    f.write_text(
        """
name: "Typo Deck"
priority: 50
mandatory:
  - "delver of secret"
""",
        encoding="utf-8",
    )
    known = {"delver of secrets", "lightning bolt"}
    errors = validate_archetype_file(f, known_cards=known)
    assert any("Unknown card 'delver of secret'" in e for e in errors)


def test_network_calls_are_blocked():
    with pytest.raises(RuntimeError, match="blocked during tests"):
        urllib.request.urlopen("https://api.scryfall.com/catalog/card-names")


def test_fetch_scryfall_from_cache_makes_no_network_call(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(["Lightning Bolt", "Counterspell"]), encoding="utf-8")
    cards = fetch_scryfall_card_names(cache_path=cache_file)
    assert "lightning bolt" in cards
    assert "counterspell" in cards


def test_fetch_scryfall_without_cache_blocked(tmp_path):
    uncached = tmp_path / "uncached.json"
    with pytest.raises(RuntimeError, match="blocked during tests"):
        fetch_scryfall_card_names(cache_path=uncached)


def test_fetch_scryfall_expired_cache_attempts_download(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(["Lightning Bolt"]), encoding="utf-8")
    # Set modification time to 8 days ago
    eight_days_ago = time.time() - (8 * 24 * 60 * 60)
    os.utime(cache_file, (eight_days_ago, eight_days_ago))

    # Because it is older than 1 week, it attempts fresh download and hits network block
    with pytest.raises(RuntimeError, match="blocked during tests"):
        fetch_scryfall_card_names(cache_path=cache_file)
