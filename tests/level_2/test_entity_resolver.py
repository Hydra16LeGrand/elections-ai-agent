"""Tests pour la résolution d'entités."""

import pytest
from unittest.mock import patch
from app.entity_resolver import EntityResolver


def test_typo_correction():
    """Une faute de frappe est corrigée."""
    with patch.object(EntityResolver, '_load_entities'):
        resolver = EntityResolver.__new__(EntityResolver)
        resolver._localities = ["TIAPOUM"]
        resolver._locality_words = {"TIAPOUM": "TIAPOUM"}
        resolver._regions = []
        resolver._parties = []
        resolver._candidates = []

        result, score = resolver.resolve_locality("Tiapam")
        assert "TIAPOUM" in result
        assert score >= 80


def test_party_alias_normalized():
    """Un alias de parti est normalisé."""
    with patch.object(EntityResolver, '_load_entities'):
        resolver = EntityResolver.__new__(EntityResolver)
        resolver._parties = ["RHDP"]

        result, _ = resolver.resolve_party("r.h.d.p")
        assert result == "RHDP"


def test_no_match_returns_original():
    """Si pas de match, retourne l'original."""
    with patch.object(EntityResolver, '_load_entities'):
        resolver = EntityResolver.__new__(EntityResolver)
        resolver._localities = ["Abidjan"]
        resolver._locality_words = {}

        result, score = resolver.resolve_locality("VilleInconnue")
        assert result == "VilleInconnue"
        assert score < 80
