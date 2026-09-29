"""Tests for mtg-archetypes CLI."""

import io
import json
from unittest.mock import patch

from mtg_archetypes.cli import main


def test_cli_default_output(tmp_path, capsys):
    deck = tmp_path / "deck.txt"
    deck.write_text(
        """
4 Delver of Secrets
4 Daze
4 Force of Will
4 Lightning Bolt
4 Volcanic Island
4 Brainstorm
""",
        encoding="utf-8",
    )

    code = main(["legacy", str(deck)])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "Izzet Delver"


def test_cli_verbose_output(tmp_path, capsys):
    deck = tmp_path / "deck.txt"
    cards = "4 Delver of Secrets\n4 Daze\n4 Lightning Bolt\n4 Volcanic Island\n4 Force of Will\n"
    deck.write_text(cards, encoding="utf-8")

    code = main(["legacy", str(deck), "--verbose"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Archetype: Izzet Delver" in captured.out
    assert "Priority:  100" in captured.out


def test_cli_json_output(tmp_path, capsys):
    deck = tmp_path / "deck.txt"
    cards = "4 Delver of Secrets\n4 Daze\n4 Lightning Bolt\n4 Volcanic Island\n4 Force of Will\n"
    deck.write_text(cards, encoding="utf-8")

    code = main(["legacy", str(deck), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["matched"] is True
    assert data["name"] == "Izzet Delver"


def test_cli_stdin(capsys):
    deck_text = (
        "4 Delver of Secrets\n4 Daze\n4 Lightning Bolt\n4 Volcanic Island\n4 Force of Will\n"
    )
    with patch("sys.stdin", io.StringIO(deck_text)):
        code = main(["legacy"])
        assert code == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "Izzet Delver"


def test_cli_unclassified_default_outputs_nothing(capsys):
    deck_text = "60 Plains\n"
    with patch("sys.stdin", io.StringIO(deck_text)):
        code = main(["legacy"])
        assert code == 0
        captured = capsys.readouterr()
        # Default behavior: outputs nothing at all on no match
        assert captured.out == ""


def test_cli_unclassified_verbose_outputs_unclassified(capsys):
    deck_text = "60 Plains\n"
    with patch("sys.stdin", io.StringIO(deck_text)):
        code = main(["legacy", "--verbose"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Archetype: Unclassified" in captured.out
