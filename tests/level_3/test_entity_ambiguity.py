"""Tests pour la detection d'ambiguite d'entites."""

import pytest
from unittest.mock import patch, MagicMock
from app.hybrid_router import detect_entity_ambiguity, route_with_fallback


def test_detect_ambiguous_locality():
    """Detecter une localite presente dans plusieurs regions."""
    with patch("app.hybrid_router.get_resolver") as mock_get_resolver:
        mock_resolver = MagicMock()
        mock_resolver.resolve_locality.return_value = ("TIAPOUM", 95.0)
        mock_resolver.is_ambiguous.return_value = (True, ["SUD-COMOE", "LAGUNES"])
        mock_get_resolver.return_value = mock_resolver

        result = detect_entity_ambiguity("Montre-moi Tiapoum")

        assert result["ambiguous"] is True
        assert result["entity_type"] == "locality"
        assert result["entity_value"] == "TIAPOUM"
        assert len(result["options"]) == 2


def test_detect_non_ambiguous_locality():
    """Localite unique, pas d'ambiguite."""
    with patch("app.hybrid_router.get_resolver") as mock_get_resolver:
        mock_resolver = MagicMock()
        mock_resolver.resolve_locality.return_value = ("ABIDJAN", 98.0)
        mock_resolver.is_ambiguous.return_value = (False, ["LAGUNES"])
        mock_get_resolver.return_value = mock_resolver

        result = detect_entity_ambiguity("Resultats a Abidjan")

        assert result is None


def test_route_with_entity_clarification():
    """Le routeur retourne entity_clarification quand ambigu."""
    with patch("app.hybrid_router.get_resolver") as mock_get_resolver:
        mock_resolver = MagicMock()
        mock_resolver.resolve_locality.return_value = ("TIAPOUM", 95.0)
        mock_resolver.is_ambiguous.return_value = (True, ["SUD-COMOE", "LAGUNES"])
        mock_get_resolver.return_value = mock_resolver

        result = route_with_fallback("Tiapoum")

        assert result["route"] == "entity_clarification"
        assert "SUD-COMOE" in result["options"]


def test_no_ambiguity_continues_to_classification():
    """Pas d'ambiguite, on continue vers SQL/RAG."""
    with patch("app.hybrid_router.get_resolver") as mock_get_resolver:
        mock_resolver = MagicMock()
        mock_resolver.resolve_locality.return_value = ("ABIDJAN", 98.0)
        mock_resolver.is_ambiguous.return_value = (False, ["LAGUNES"])
        mock_get_resolver.return_value = mock_resolver

    with patch("app.hybrid_router.classify_question") as mock_classify:
        mock_classify.return_value = {
            "route": "sql",
            "confidence": 0.95,
            "reasoning": "Question chiffree"
        }

        result = route_with_fallback("Combien a Abidjan")

        assert result["route"] == "sql"
