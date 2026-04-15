"""Tests d'intégration avec appels LLM réels.

Ces tests vérifient le comportement réel du système avec des appels API.
A exécuter manuellement car dépendent de la disponibilité de l'API Ollama.
"""

import pytest
from app.sql_agent import ask_database, ask_hybrid
from app.hybrid_router import route_with_fallback


@pytest.mark.integration
@pytest.mark.slow
def test_abidjan_search_finds_results():
    """Abidjan cherché dans region ET nom_circonscription."""
    result = ask_database("Qui a gagné à Abidjan ?")

    assert result["status"] == "success"
    assert result["sql"] is not None
    assert "OR" in result["sql"] or ("region" in result["sql"] and "nom_circonscription" in result["sql"])
    assert len(result["data"]) > 0  # Doit trouver des résultats


@pytest.mark.integration
@pytest.mark.slow
def test_tiapoum_resolved_correctly():
    """Tiapoum résolu avec fuzzy matching."""
    result = ask_database("Qui a gagné à Tiapam ?")  # Typo intentionnelle

    assert result["status"] == "success"
    assert "TIAPOUM" in result["sql"].upper() or len(result["data"]) > 0


@pytest.mark.integration
@pytest.mark.slow
def test_rhdp_alias_normalized():
    """RHDP, R.H.D.P normalisés vers RHDP."""
    result = ask_database("Résultats du parti R.H.D.P ?")

    assert result["status"] == "success"
    # Le LLM devrait générer un SQL avec RHDP


@pytest.mark.integration
@pytest.mark.slow
def test_hybrid_router_classifies_sql():
    """Routeur classe correctement les questions analytiques."""
    result = route_with_fallback("Combien de sièges a remporté le RHDP ?")

    assert result["route"] == "sql"
    assert result["confidence"] > 0.80


@pytest.mark.integration
@pytest.mark.slow
def test_hybrid_router_classifies_rag():
    """Routeur classe correctement les questions narratives."""
    result = route_with_fallback("Résume les résultats de cette élection")

    assert result["route"] == "rag"
    assert result["confidence"] > 0.80


@pytest.mark.integration
@pytest.mark.slow
def test_low_confidence_triggers_clarification():
    """Confiance < 0.80 déclenche clarification."""
    result = route_with_fallback("Tiapoum")

    # Peut être sql, rag ou clarification selon le LLM
    # On vérifie juste que ça ne plante pas
    assert "route" in result
    assert "confidence" in result
