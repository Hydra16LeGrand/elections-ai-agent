"""Tests pour le hybrid router."""

import pytest
from unittest.mock import patch
from app.hybrid_router import classify_question, route_with_fallback


def test_sql_question_routed():
    """Une question analytique est routée vers SQL."""
    with patch("app.hybrid_router.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"route": "sql", "confidence": 0.95}'}
        }
        result = classify_question("Combien de bulletins nuls?")
        assert result["route"] == "sql"


def test_rag_question_routed():
    """Une question narrative est routée vers RAG."""
    with patch("app.hybrid_router.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"route": "rag", "confidence": 0.92}'}
        }
        result = classify_question("Résume les résultats")
        assert result["route"] == "rag"


def test_low_confidence_triggers_clarification():
    """Une confiance < 0.80 demande clarification."""
    with patch("app.hybrid_router.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"route": "sql", "confidence": 0.65}'}
        }
        result = route_with_fallback("Parle-moi des élections")
        assert result["route"] == "clarification"
