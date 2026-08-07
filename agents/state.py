"""Compatibility shim re-exporting state contract from the unified state package."""

from state import AgentState, StateContract, build_state  # noqa: F401

__all__ = ["AgentState", "StateContract", "build_state"]

