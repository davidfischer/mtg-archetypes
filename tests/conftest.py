"""Pytest fixtures and configuration."""

import socket
from pathlib import Path

import pytest

from mtg_archetypes.engine import ArchetypeClassifier


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Ensure no tests make network calls or DNS lookups."""

    def _guarded_connect(self, *args, **kwargs):
        raise RuntimeError(f"Network call blocked during tests: connect{args}")

    def _guarded_getaddrinfo(*args, **kwargs):
        raise RuntimeError(f"DNS lookup blocked during tests: getaddrinfo{args}")

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)


@pytest.fixture
def sample_rules_dir() -> Path:
    """Path to fixture rules directory containing well-defined archetype rules for testing."""
    return Path(__file__).parent / "fixtures" / "archetypes"


@pytest.fixture
def classifier(sample_rules_dir: Path) -> ArchetypeClassifier:
    """ArchetypeClassifier loaded with sample test rules."""
    return ArchetypeClassifier(rules_dir=sample_rules_dir)


@pytest.fixture
def repo_classifier() -> ArchetypeClassifier:
    """ArchetypeClassifier loaded with production rules from the repository."""
    return ArchetypeClassifier()
