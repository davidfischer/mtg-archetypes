"""Tests for ArchetypeClassifier."""

import pytest

from mtg_archetypes.engine import ArchetypeClassifier
from mtg_archetypes.engine import ArchetypeRule
from mtg_archetypes.engine import CardRequirement
from mtg_archetypes.engine import ClassificationResult
from mtg_archetypes.engine import SignatureGroup


@pytest.fixture
def classifier():
    return ArchetypeClassifier()


def test_classify_matched_rule(classifier):
    """Deck with Delver and signatures matches Izzet Delver."""
    mainboard = [
        "Delver of Secrets",
        "Daze",
        "Lightning Bolt",
        "Force of Will",
        "Volcanic Island",
        "Brainstorm",
    ]
    res = classifier.classify(mainboard, format="legacy")
    assert isinstance(res, ClassificationResult)
    assert res.matched is True
    assert res.name == "Izzet Delver"
    assert res.priority == 100


def test_classify_unclassified(classifier):
    """Deck with random cards that matches no rules returns matched=False with name=None."""
    mainboard = [
        "Plains",
        "Grizzly Bears",
        "Healing Salve",
    ]
    res = classifier.classify(mainboard, format="legacy")
    assert res.matched is False
    assert res.name is None
    assert res.slug is None
    assert res.priority == 0


def test_scoped_mandatory_main_vs_side(tmp_path):
    """Test 'in = main' and 'in = side' on mandatory cards."""
    vintage_dir = tmp_path / "vintage"
    vintage_dir.mkdir(parents=True)

    yaml_content = """
name: "Lurrus Test"
priority: 90

mandatory:
  - card: "Lurrus of the Dream-Den"
    in: "side"
  - card: "Black Lotus"
    in: "main"
"""
    (vintage_dir / "lurrus-test.yaml").write_text(yaml_content, encoding="utf-8")
    cf = ArchetypeClassifier(rules_dir=tmp_path)

    # Lurrus in mainboard instead of sideboard -> fails rule
    res_fail = cf.classify(
        mainboard_cards=["Black Lotus", "Lurrus of the Dream-Den"],
        sideboard_cards=["Swords to Plowshares"],
        format="vintage",
    )
    assert res_fail.matched is False

    # Lurrus in sideboard, Lotus in mainboard -> matches rule!
    res_pass = cf.classify(
        mainboard_cards=["Black Lotus", "Mox Sapphire"],
        sideboard_cards=["Lurrus of the Dream-Den"],
        format="vintage",
    )
    assert res_pass.matched is True
    assert res_pass.name == "Lurrus Test"


def test_scoped_anti_signatures(tmp_path):
    """Test anti_signatures with 'in = main'."""
    vintage_dir = tmp_path / "vintage"
    vintage_dir.mkdir(parents=True)

    yaml_content = """
name: "Raker Test"
priority: 95

mandatory:
  - card: "Mishra's Workshop"
    min: 3
    in: "main"

anti_signatures:
  - card: "Sphere of Resistance"
    in: "main"
"""
    (vintage_dir / "raker-test.yaml").write_text(yaml_content, encoding="utf-8")
    cf = ArchetypeClassifier(rules_dir=tmp_path)

    # Sphere in mainboard -> fails anti_signature
    res_mb_sphere = cf.classify(
        mainboard_cards=[{"card": "Mishra's Workshop", "count": 4}, "Sphere of Resistance"],
        sideboard_cards=["Tormod's Crypt"],
        format="vintage",
    )
    assert res_mb_sphere.matched is False

    # Sphere in sideboard -> allowed because anti_signature is scoped to main!
    res_sb_sphere = cf.classify(
        mainboard_cards=[{"card": "Mishra's Workshop", "count": 4}, "Chalice of the Void"],
        sideboard_cards=["Sphere of Resistance"],
        format="vintage",
    )
    assert res_sb_sphere.matched is True
    assert res_sb_sphere.name == "Raker Test"


def test_signature_groups(tmp_path):
    """Test multiple signature groups evaluated with AND logic."""
    vintage_dir = tmp_path / "vintage"
    vintage_dir.mkdir(parents=True)

    yaml_content = """
name: "CounterVine Test"
priority: 95

mandatory:
  - card: "Bazaar of Baghdad"
    min: 3
    in: "main"

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
"""
    (vintage_dir / "countervine-test.yaml").write_text(yaml_content, encoding="utf-8")
    cf = ArchetypeClassifier(rules_dir=tmp_path)

    # Only group 1 satisfied (0 rootwallas) -> fails
    res_no_root = cf.classify(
        mainboard_cards=[{"card": "Bazaar of Baghdad", "count": 4}, "Master of Death"],
        format="vintage",
    )
    assert res_no_root.matched is False

    # Both groups satisfied -> matches!
    res_both = cf.classify(
        mainboard_cards=[
            {"card": "Bazaar of Baghdad", "count": 4},
            "Master of Death",
            "Basking Rootwalla",
            "Blazing Rootwalla",
        ],
        format="vintage",
    )
    assert res_both.matched is True
    assert res_both.name == "CounterVine Test"


def test_dfc_name_handling(classifier):
    """Canonical DFC name matches rules written as front face."""
    mainboard = [
        "Delver of Secrets // Insectile Aberration",
        "Daze",
        "Force of Will",
        "Lightning Bolt",
        "Volcanic Island",
    ]
    res = classifier.classify(mainboard, format="legacy")
    assert res.matched is True
    assert res.name == "Izzet Delver"


def test_default_min_signatures_is_one(tmp_path):
    """When min_signatures is omitted, it defaults to 1."""
    fmt_dir = tmp_path / "legacy"
    fmt_dir.mkdir(parents=True)

    yaml_content = """
name: "Sig Default Test"
priority: 50
signatures:
  - "Brainstorm"
  - "Ponder"
  - "Preordain"
"""
    (fmt_dir / "sig-test.yaml").write_text(yaml_content, encoding="utf-8")
    cf = ArchetypeClassifier(rules_dir=tmp_path)

    # Deck with 0 signatures -> no match
    res_zero = cf.classify(["Plains"], format="legacy")
    assert res_zero.matched is False

    # Deck with 1 signature card -> matches because min_signatures defaults to 1
    res_one = cf.classify(["Brainstorm"], format="legacy")
    assert res_one.matched is True
    assert res_one.name == "Sig Default Test"


def test_mtgo_card_dict_format(classifier):
    """Deck input using MTGO {"CardName": str, "Count": int} format is properly parsed."""
    mainboard = [
        {"CardName": "Delver of Secrets", "Count": 4},
        {"CardName": "Daze", "Count": 4},
        {"CardName": "Force of Will", "Count": 4},
        {"CardName": "Lightning Bolt", "Count": 4},
        {"CardName": "Volcanic Island", "Count": 4},
        {"CardName": "Brainstorm", "Count": 4},
    ]
    res = classifier.classify(mainboard, format="legacy")
    assert res.matched is True
    assert res.name == "Izzet Delver"


def test_get_rules_returns_archetype_rule_dataclasses(classifier):
    """get_rules returns a list of ArchetypeRule dataclass instances."""
    rules = classifier.get_rules("legacy")
    assert len(rules) > 0
    delver_rule = next(r for r in rules if r.name == "Izzet Delver")
    assert isinstance(delver_rule, ArchetypeRule)
    assert delver_rule.priority == 100
    assert delver_rule.slug == "izzet-delver"
    assert isinstance(delver_rule.mandatory, tuple)
    assert all(isinstance(m, CardRequirement) for m in delver_rule.mandatory)
    assert isinstance(delver_rule.signatures, frozenset)
    assert isinstance(delver_rule.signature_groups, tuple)
    assert all(isinstance(g, SignatureGroup) for g in delver_rule.signature_groups)
    assert isinstance(delver_rule.anti_signatures, tuple)
    assert all(isinstance(a, CardRequirement) for a in delver_rule.anti_signatures)


def test_higher_priority_matches_first(tmp_path):
    """Higher priority rule matches first regardless of signature counts."""
    fmt_dir = tmp_path / "legacy"
    fmt_dir.mkdir(parents=True)

    # Specific rule: priority 100, requires 1 signature
    (fmt_dir / "delver.yaml").write_text(
        """
name: "Delver"
priority: 100
signatures:
  - "Delver of Secrets"
""",
        encoding="utf-8",
    )

    # Broad rule: priority 80, matches many cards
    (fmt_dir / "blue-control.yaml").write_text(
        """
name: "Blue Control"
priority: 80
signatures:
  - "Delver of Secrets"
  - "Brainstorm"
  - "Ponder"
  - "Force of Will"
""",
        encoding="utf-8",
    )

    cf = ArchetypeClassifier(rules_dir=tmp_path)
    res = cf.classify(
        ["Delver of Secrets", "Brainstorm", "Ponder", "Force of Will"],
        format="legacy",
    )
    # Delver has higher priority (100 vs 80) and matches first
    assert res.matched is True
    assert res.name == "Delver"
    assert res.priority == 100
