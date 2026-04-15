"""Pydantic models for pipeline YAML files.

A Pipeline is a directed graph of Nodes connected by Edges. Nodes are
executed by handlers registered in `factory.pipeline.handlers`. Edges
carry optional `when` conditions that gate traversal based on the
previous node's result.
"""

from __future__ import annotations

from typing import Any
from typing import Literal

import yaml
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator


class RetryPolicy(BaseModel):
    """Retry behavior for a node."""

    max: int = Field(default=1, ge=1, description="Max attempts including first")
    on_exhausted: Literal["abort", "continue", "escalate"] = "abort"


class Node(BaseModel):
    """A node in the pipeline graph.

    `handler` names a function registered in `factory.pipeline.handlers`.
    `params` is a free-form dict passed to that handler at runtime —
    per-handler validation lives inside the handler, keeping the schema
    open for new handler types without edits here.
    """

    id: str
    handler: str
    params: dict[str, Any] = Field(default_factory=dict)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)


class Edge(BaseModel):
    """A directed edge between two nodes.

    `when` is an optional expression evaluated against the prior node's
    result; if omitted the edge is unconditional. The expression is a
    string like `status == "success"` — evaluated safely against the
    NodeResult's public fields only (no arbitrary Python).
    """

    from_: str = Field(alias="from")
    to: str
    when: str | None = None

    model_config = {"populate_by_name": True}


class Pipeline(BaseModel):
    """Top-level pipeline definition loaded from YAML."""

    name: str
    description: str = ""
    start: str = Field(description="ID of the entry node")
    nodes: list[Node]
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph(self) -> Pipeline:
        ids = {n.id for n in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node ids")
        if self.start not in ids:
            raise ValueError(f"start node {self.start!r} not in nodes")
        for edge in self.edges:
            if edge.from_ not in ids:
                raise ValueError(f"edge from unknown node: {edge.from_}")
            if edge.to not in ids:
                raise ValueError(f"edge to unknown node: {edge.to}")
        return self

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)

    def outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.from_ == node_id]

    @classmethod
    def from_yaml(cls, path: str) -> Pipeline:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


class NodeResult(BaseModel):
    """Result of executing a single node."""

    status: Literal["success", "failed", "skipped"]
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
