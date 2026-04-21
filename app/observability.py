"""Module de tracing pour l'observability end-to-end."""
import json
import time
from datetime import datetime
from typing import Any, Optional
from contextlib import contextmanager


class RequestTracer:
    """Capture les événements d'une requête utilisateur de bout en bout."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or self._generate_id()
        self.start_time = time.time()
        self.events = []
        self.metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": self.request_id
        }

    def _generate_id(self) -> str:
        """Génère un ID unique simple."""
        return f"req_{int(time.time() * 1000)}"

    def log_event(self, stage: str, data: dict, duration_ms: Optional[float] = None):
        """Ajoute un événement au trace."""
        event = {
            "stage": stage,
            "timestamp": time.time(),
            "data": data
        }
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
        self.events.append(event)

    def log_intent_classification(self, question: str, intent: str,
                                   confidence: float, reasoning: str = ""):
        """Log l'étape de classification d'intent."""
        self.log_event("intent_classification", {
            "question": question,
            "intent": intent,
            "confidence": confidence,
            "reasoning": reasoning
        })

    def log_rag_retrieval(self, query: str, chunks: list,
                          retrieval_time_ms: float):
        """Log les résultats RAG."""
        self.log_event("rag_retrieval", {
            "query": query,
            "chunks_count": len(chunks),
            "chunks": [
                {
                    "text": c.get("text", "")[:200],
                    "score": c.get("score"),
                    "metadata": c.get("metadata", {})
                }
                for c in chunks[:5]  # Limite pour garder le JSON léger
            ]
        }, duration_ms=retrieval_time_ms)

    def log_sql_generation(self, question: str, sql: str,
                           generation_time_ms: float, attempt: int = 1):
        """Log la génération SQL."""
        self.log_event("sql_generation", {
            "question": question,
            "sql": sql,
            "attempt": attempt
        }, duration_ms=generation_time_ms)

    def log_sql_validation(self, sql: str, is_safe: bool,
                         error: str = "", modified_sql: str = ""):
        """Log le résultat des guardrails."""
        self.log_event("sql_validation", {
            "original_sql": sql,
            "is_safe": is_safe,
            "error": error,
            "modified_sql": modified_sql if modified_sql else None
        })

    def log_sql_execution(self, sql: str, row_count: int,
                         execution_time_ms: float, error: str = ""):
        """Log l'exécution SQL."""
        self.log_event("sql_execution", {
            "sql": sql,
            "row_count": row_count,
            "error": error if error else None
        }, duration_ms=execution_time_ms)

    def log_synthesis(self, chart_type: str, synthesis_time_ms: float):
        """Log la synthèse et choix de graphique."""
        self.log_event("synthesis", {
            "chart_type": chart_type
        }, duration_ms=synthesis_time_ms)

    def log_final_response(self, status: str, token_usage: dict = None):
        """Log la réponse finale avec métriques."""
        total_time = (time.time() - self.start_time) * 1000
        self.log_event("final_response", {
            "status": status,
            "total_time_ms": total_time,
            "token_usage": token_usage or {}
        })

    def export_json(self) -> str:
        """Exporte le trace au format JSON."""
        total_time = (time.time() - self.start_time) * 1000
        export = {
            "metadata": self.metadata,
            "total_duration_ms": total_time,
            "event_count": len(self.events),
            "events": self.events
        }
        return json.dumps(export, indent=2, default=str)

    def to_dict(self) -> dict:
        """Retourne le trace sous forme de dict."""
        total_time = (time.time() - self.start_time) * 1000
        return {
            "metadata": self.metadata,
            "total_duration_ms": total_time,
            "event_count": len(self.events),
            "events": self.events
        }


@contextmanager
def timed_stage(tracer: RequestTracer, stage_name: str, data: dict = None):
    """Context manager pour mesurer automatiquement la durée d'une étape."""
    start = time.time()
    data = data or {}
    error = None

    try:
        yield data
    except Exception as e:
        error = str(e)
        raise
    finally:
        duration = (time.time() - start) * 1000
        if error:
            data["error"] = error
        tracer.log_event(stage_name, data, duration_ms=duration)


def save_trace_to_file(trace: RequestTracer, output_dir: str = ".traces"):
    """Sauvegarde le trace dans un fichier JSON."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{trace.request_id}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(trace.export_json())

    return filepath