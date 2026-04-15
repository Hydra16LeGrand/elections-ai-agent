"""Session memory for storing user entity resolutions."""

from typing import Optional, Dict, Any
import streamlit as st


class SessionMemory:
    """Stores entity resolutions during a Streamlit session."""

    def __init__(self):
        self._store: Dict[tuple, Dict[str, Any]] = {}

    def store(self, entity_type: str, entity_value: str, context: dict) -> None:
        """Store a resolution context for an entity."""
        key = (entity_type.lower(), entity_value.upper())
        self._store[key] = context

    def get(self, entity_type: str, entity_value: str) -> Optional[dict]:
        """Retrieve stored context for an entity."""
        key = (entity_type.lower(), entity_value.upper())
        return self._store.get(key)

    def has(self, entity_type: str, entity_value: str) -> bool:
        """Check if we have stored info for this entity."""
        key = (entity_type.lower(), entity_value.upper())
        return key in self._store

    def clear(self) -> None:
        """Clear all stored resolutions."""
        self._store.clear()


def get_session_memory() -> SessionMemory:
    """Get or create the singleton SessionMemory instance."""
    if "_session_memory" not in st.session_state:
        st.session_state._session_memory = SessionMemory()
    return st.session_state._session_memory
