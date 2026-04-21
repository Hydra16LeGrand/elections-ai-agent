"""Tests basiques pour le module d'observability."""
import json
import time
import pytest
from app.observability import RequestTracer, timed_stage


def test_tracer_initialization():
    """Vérifie qu'un tracer se crée avec un ID unique."""
    tracer = RequestTracer()
    assert tracer.request_id is not None
    assert tracer.request_id.startswith("req_")
    assert len(tracer.events) == 0


def test_tracer_with_custom_id():
    """Vérifie qu'on peut passer un ID personnalisé."""
    tracer = RequestTracer(request_id="custom_123")
    assert tracer.request_id == "custom_123"


def test_log_intent_classification():
    """Vérifie le logging de classification d'intent."""
    tracer = RequestTracer()
    tracer.log_intent_classification(
        question="Qui a gagné à Abidjan ?",
        intent="valid",
        confidence=0.95,
        reasoning="Question sur résultats électoraux"
    )

    assert len(tracer.events) == 1
    event = tracer.events[0]
    assert event["stage"] == "intent_classification"
    assert event["data"]["intent"] == "valid"
    assert event["data"]["confidence"] == 0.95


def test_log_sql_validation():
    """Vérifie le logging de validation SQL."""
    tracer = RequestTracer()
    tracer.log_sql_validation(
        sql="SELECT * FROM vw_winners",
        is_safe=True,
        modified_sql="SELECT * FROM vw_winners LIMIT 100"
    )

    event = tracer.events[0]
    assert event["stage"] == "sql_validation"
    assert event["data"]["is_safe"] is True


def test_log_sql_validation_blocked():
    """Vérifie le logging quand la requête est bloquée."""
    tracer = RequestTracer()
    tracer.log_sql_validation(
        sql="DROP TABLE users",
        is_safe=False,
        error="Opération destructive"
    )

    event = tracer.events[0]
    assert event["data"]["is_safe"] is False
    assert "DROP TABLE users" in event["data"]["original_sql"]


def test_log_rag_retrieval():
    """Vérifie le logging des résultats RAG."""
    tracer = RequestTracer()
    chunks = [
        {"text": "Résultat 1", "score": 0.95, "metadata": {"page": 1}},
        {"text": "Résultat 2", "score": 0.87, "metadata": {"page": 2}}
    ]
    tracer.log_rag_retrieval(
        query="candidat Abidjan",
        chunks=chunks,
        retrieval_time_ms=150.5
    )

    event = tracer.events[0]
    assert event["stage"] == "rag_retrieval"
    assert event["data"]["chunks_count"] == 2
    assert event["duration_ms"] == 150.5


def test_log_final_response():
    """Vérifie le logging de la réponse finale."""
    tracer = RequestTracer()
    time.sleep(0.01)  # Petit délai pour tester le timing

    tracer.log_final_response("success", {"input": 10, "output": 50})

    event = tracer.events[0]
    assert event["stage"] == "final_response"
    assert event["data"]["status"] == "success"
    assert event["data"]["token_usage"]["input"] == 10
    assert event["data"]["total_time_ms"] > 0


def test_timed_stage_context_manager():
    """Vérifie le context manager pour mesurer les étapes."""
    tracer = RequestTracer()

    with timed_stage(tracer, "test_stage", {"info": "test"}):
        time.sleep(0.01)

    event = tracer.events[0]
    assert event["stage"] == "test_stage"
    assert event["data"]["info"] == "test"
    assert event["duration_ms"] >= 10  # Au moins 10ms


def test_timed_stage_with_exception():
    """Vérifie que le context manager log même en cas d'exception."""
    tracer = RequestTracer()

    try:
        with timed_stage(tracer, "failing_stage"):
            raise ValueError("Test error")
    except ValueError:
        pass

    event = tracer.events[0]
    assert event["stage"] == "failing_stage"
    assert "Test error" in event["data"]["error"]


def test_export_json():
    """Vérifie l'export JSON."""
    tracer = RequestTracer(request_id="test_export")
    tracer.log_intent_classification("Q?", "valid", 0.9)
    tracer.log_final_response("success")

    json_output = tracer.export_json()
    data = json.loads(json_output)

    assert data["metadata"]["request_id"] == "test_export"
    assert data["event_count"] == 2
    assert data["total_duration_ms"] > 0
    assert len(data["events"]) == 2


def test_to_dict():
    """Vérifie la conversion en dict."""
    tracer = RequestTracer(request_id="test_dict")
    tracer.log_event("test", {"key": "value"})

    result = tracer.to_dict()
    assert result["metadata"]["request_id"] == "test_dict"
    assert result["events"][0]["stage"] == "test"