"""Tests pour les guardrails SQL."""

import pytest
from app.sql_agent import apply_guardrails


def test_valid_query_passes():
    """Une requête valide passe les guardrails."""
    query = "SELECT * FROM vw_winners WHERE region = 'Abidjan'"
    is_safe, _, error = apply_guardrails(query)
    assert is_safe is True
    assert error == ""


def test_drop_blocked():
    """DROP TABLE est bloqué."""
    query = "DROP TABLE users"
    is_safe, _, error = apply_guardrails(query)
    assert is_safe is False
    assert "destructive" in error.lower()


def test_limit_added_automatically():
    """LIMIT 100 est ajouté si manquant."""
    query = "SELECT * FROM vw_winners"
    _, final_sql, _ = apply_guardrails(query)
    assert "LIMIT 100" in final_sql


def test_raw_table_blocked():
    """L'accès à la table brute est bloqué."""
    query = "SELECT * FROM raw_election_data"
    is_safe, _, _ = apply_guardrails(query)
    assert is_safe is False


def test_aggregation_no_limit():
    """Pas de LIMIT ajouté aux agrégations."""
    query = "SELECT COUNT(*) FROM vw_winners"
    _, final_sql, _ = apply_guardrails(query)
    assert "LIMIT" not in final_sql.upper()
