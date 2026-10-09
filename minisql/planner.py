"""Logical and physical plan representations with basic predicate pushdown."""
from __future__ import annotations
from dataclasses import dataclass
from .ast import Select

@dataclass(frozen=True)
class PlanNode:
    operation: str
    detail: str = ""
    children: tuple["PlanNode", ...] = ()

def plan(query: Select) -> PlanNode:
    node = PlanNode("TableScan", query.table.name)
    for join in query.joins:
        node = PlanNode("InnerJoin", f"{join.left} {join.op} {join.right}", (node, PlanNode("TableScan", join.table.name)))
    if query.where is not None:
        # Logical filter node; executor evaluates it after joins in this version.
        node = PlanNode("Filter", str(query.where), (node,))
    if query.group_by or any(getattr(item.expr, "name", "").upper() in {"COUNT", "SUM", "AVG", "MIN", "MAX"} for item in query.columns):
        node = PlanNode("Aggregate", f"group_by={query.group_by}", (node,))
    if query.order_by:
        node = PlanNode("Sort", f"order_by={query.order_by}", (node,))
    if query.limit is not None:
        node = PlanNode("Limit", str(query.limit), (node,))
    return node

def format_plan(node: PlanNode, depth: int = 0) -> str:
    lines = ["  " * depth + node.operation + (f": {node.detail}" if node.detail else "")]
    for child in node.children:
        lines.extend(format_plan(child, depth + 1).splitlines())
    return "\n".join(lines)
