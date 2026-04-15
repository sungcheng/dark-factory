"""Pipeline schema validation tests."""

from __future__ import annotations

import pytest

from factory.pipeline.schema import Edge
from factory.pipeline.schema import Node
from factory.pipeline.schema import Pipeline


def _pipeline(nodes: list[Node], edges: list[Edge], start: str = "a") -> Pipeline:
    return Pipeline(name="t", start=start, nodes=nodes, edges=edges)


def test_pipeline_validates_start_node_exists() -> None:
    with pytest.raises(ValueError, match="not in nodes"):
        _pipeline(
            [Node(id="a", handler="shell")],
            [],
            start="missing",
        )


def test_pipeline_rejects_duplicate_node_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        _pipeline(
            [Node(id="a", handler="shell"), Node(id="a", handler="shell")],
            [],
        )


def test_pipeline_rejects_edge_to_unknown_node() -> None:
    with pytest.raises(ValueError, match="edge to unknown"):
        _pipeline(
            [Node(id="a", handler="shell")],
            [Edge(**{"from": "a", "to": "b"})],
        )


def test_edge_uses_from_alias() -> None:
    edge = Edge(**{"from": "a", "to": "b"})
    assert edge.from_ == "a"


def test_pipeline_outgoing_returns_edges_from_node() -> None:
    p = _pipeline(
        [Node(id="a", handler="shell"), Node(id="b", handler="shell")],
        [Edge(**{"from": "a", "to": "b"})],
    )
    assert len(p.outgoing("a")) == 1
    assert p.outgoing("b") == []
