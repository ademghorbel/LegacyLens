"""New LangGraph Agent.

This module defines a custom graph.
"""

# ponytail: lazy import — graph instantiation happens in graph.py, not here
# importing at module level would build the graph before .env is loaded
__all__ = ["graph", "create_graph", "State"]


def __getattr__(name):
    if name in __all__:
        from agent import graph as _mod
        return getattr(_mod, name)
    raise AttributeError(f"module 'agent' has no attribute {name!r}")
