"""Tests pour le moteur RAG."""

import pytest
from unittest.mock import patch, MagicMock
from app.rag_engine import RAGEngine, query_rag


def test_rag_query_returns_response():
    """Une requête RAG retourne une réponse."""
    with patch.object(RAGEngine, '_build_index'):
        engine = RAGEngine(skip_index_build=True)
        engine.index = MagicMock()
        engine._index_built = True

        mock_node = MagicMock()
        mock_node.text = "Résultats électoraux..."
        mock_node.metadata = {'region': 'SUD-COMOE'}
        engine.index.as_retriever.return_value.retrieve.return_value = [mock_node]

        with patch("app.rag_engine.client") as mock_client:
            mock_client.chat.return_value = {
                "message": {"content": "Le candidat X a été élu."}
            }

            result = engine.query("Résume les résultats")
            assert result['status'] == 'success'
            assert result['route'] == 'rag'


def test_rag_no_index_returns_error():
    """Si pas d'index, retourne une erreur."""
    with patch.object(RAGEngine, '_build_index'):
        engine = RAGEngine(skip_index_build=True)
        engine.index = None

        result = engine.query("Résume")
        assert result['status'] == 'error'


def test_rag_singleton():
    """Le singleton retourne la même instance."""
    with patch.object(RAGEngine, '_build_index'):
        from app.rag_engine import get_rag_engine
        engine1 = get_rag_engine()
        engine2 = get_rag_engine()
        assert engine1 is engine2
