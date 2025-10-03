"""Minimal LangGraph example that increments a counter until it reaches three."""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph


class CounterState(TypedDict):
    count: int


def increment(state: CounterState) -> CounterState:
    updated = state["count"] + 1
    return {"count": updated}


def should_stop(state: CounterState) -> bool:
    return state["count"] >= 3


def build_app():
    graph = StateGraph(CounterState)
    graph.add_node("increment", increment)
    graph.set_entry_point("increment")
    graph.add_conditional_edges(
        "increment",
        should_stop,
        {True: END, False: "increment"},
    )
    return graph.compile()


if __name__ == "__main__":
    app = build_app()
    for step, event in enumerate(app.stream({"count": 0}), start=1):
        print(f"step {step}: {event}")
