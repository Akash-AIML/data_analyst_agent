"""Canonical shared state package. Re-exports the AgentState contract, StateContract, and build_state."""

from state.graph_state import AgentState, StateContract, build_state  # noqa: F401

__all__ = ["AgentState", "StateContract", "build_state"]

