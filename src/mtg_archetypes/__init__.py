"""mtg-archetypes: Magic: The Gathering deck archetype classifier"""

from .cards import expand_card_counts
from .cards import normalize_card_name
from .cards import parse_decklist_text
from .cards import slugify_archetype
from .engine import ArchetypeClassifier
from .engine import ArchetypeRule
from .engine import CardRequirement
from .engine import ClassificationResult
from .engine import SignatureGroup


__version__ = "2026.9.2"

__all__ = [
    "ArchetypeClassifier",
    "ArchetypeRule",
    "CardRequirement",
    "ClassificationResult",
    "SignatureGroup",
    "__version__",
    "expand_card_counts",
    "normalize_card_name",
    "parse_decklist_text",
    "slugify_archetype",
]
