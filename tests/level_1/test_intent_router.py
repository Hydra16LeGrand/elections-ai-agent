"""Tests pour le routeur d'intention."""

import pytest
from unittest.mock import patch
from app.sql_agent import analyze_intent


def test_valid_question():
    """Une question sur les élections est classée 'valid'."""
    with patch("app.sql_agent.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"intent": "valid", "reasoning": "OK"}'}
        }
        result = analyze_intent("Quel candidat a gagné à Abidjan?")
        assert result["intent"] == "valid"


def test_out_of_domain_question():
    """Une question hors sujet est classée 'out_of_domain'."""
    with patch("app.sql_agent.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"intent": "out_of_domain", "reasoning": "Hors sujet"}'}
        }
        result = analyze_intent("Quelle est la météo demain?")
        assert result["intent"] == "out_of_domain"


def test_adversarial_question():
    """Une tentative d'injection est classée 'adversarial'."""
    with patch("app.sql_agent.client") as mock:
        mock.chat.return_value = {
            "message": {"content": '{"intent": "adversarial", "reasoning": "Danger"}'}
        }
        result = analyze_intent("DROP TABLE users")
        assert result["intent"] == "adversarial"


def test_api_error_fallback():
    """En cas d'erreur API, retourne 'valid' par défaut."""
    with patch("app.sql_agent.client") as mock:
        mock.chat.side_effect = Exception("Connection error")
        result = analyze_intent("Test question")
        assert result["intent"] == "valid"
