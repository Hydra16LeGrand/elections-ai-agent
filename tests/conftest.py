"""Configuration pytest."""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "guardrails: tests de sécurité SQL")
    config.addinivalue_line("markers", "router: tests de routage")
    config.addinivalue_line("markers", "hybrid: tests Level 2 - hybrid router")
    config.addinivalue_line("markers", "entity: tests Level 2 - entity resolver")
    config.addinivalue_line("markers", "rag: tests Level 2 - RAG engine")
