"""Tests pour le session memory."""

import pytest
from unittest.mock import MagicMock, patch
from app.session_memory import SessionMemory


def test_store_and_get():
    """Stocker et recuperer un contexte."""
    memory = SessionMemory()
    memory.store("locality", "Tiapoum", {"region": "SUD-COMOE"})

    result = memory.get("locality", "tiapoum")
    assert result == {"region": "SUD-COMOE"}


def test_has_existing_entity():
    """Verifier si une entite existe en memoire."""
    memory = SessionMemory()
    memory.store("locality", "Korhogo", {"region": "SAVANES"})

    assert memory.has("locality", "korhogo") is True
    assert memory.has("locality", "inconnu") is False


def test_clear_memory():
    """Vider la memoire."""
    memory = SessionMemory()
    memory.store("locality", "Abidjan", {"region": "LAGUNES"})
    memory.clear()

    assert memory.has("locality", "abidjan") is False
    assert memory.get("locality", "abidjan") is None


def test_case_insensitive():
    """La casse n'a pas d'importance."""
    memory = SessionMemory()
    memory.store("locality", "ABIDJAN", {"region": "LAGUNES"})

    assert memory.has("locality", "abidjan") is True
    assert memory.has("LOCALITY", "Abidjan") is True
