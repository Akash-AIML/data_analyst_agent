"""Canonical shared state package. Re-exports the AgentState contract."""

from state.graph_state import AgentState  # noqa: F401

__all__ = ["AgentState"]
