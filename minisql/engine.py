"""Query executor for a documented SQL subset."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass
from typing import Any
from .ast import Binary, Expr, Function, Identifier, Literal, Select, Star, Unary
from .parser import parse
from .planner import format_plan, plan
from .storage import TableCatalog

class SQLExecutionError(ValueError):
    pass

@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    elapsed_seconds: float
    plan: str

def _lookup(row: dict[str, Any], name: str) -> Any:
    if name in row:
        return row[name]
    lower = name.lower()
    matches = [v for k, v in row.items() if k.lower() == lower]
    if len(matches) == 1:
        return matches[0]
    if "." in name:
        tail = name.split(".", 1)[1]
        return _lookup(row, tail)
    raise SQLExecutionError(f"unknown or ambiguous column {name!r}")

def _coerce_pair(a: Any, b: Any) -> tuple[Any, Any]:
    if isinstance(a, str) and isinstance(b, (int, float)):
        try: a = float(a)
        except ValueError: pass
    if isinstance(b, str) and isinstance(a, (int, float)):
        try: b = float(b)
        except ValueError: pass
    return a, b

def _eval(expr: Expr, row: dict[str, Any]) -> Any:
    if isinstance(expr, Literal):
        return expr.value
    if isinstance(expr, Identifier):
        return _lookup(row, expr.name)
    if isinstance(expr, Star):
        return row
    if isinstance(expr, Unary):
        value = _eval(expr.expr, row)
        if expr.op == "NOT": return not bool(value)
        if expr.op == "-": return -value
        if expr.op == "+": return +value
    if isinstance(expr, Binary):
        left = _eval(expr.left, row)
        if expr.op == "AND": return bool(left) and bool(_eval(expr.right, row))
        if expr.op == "OR": return bool(left) or bool(_eval(expr.right, row))
        right = _eval(expr.right, row)
        if expr.op in ("IS NULL", "IS NOT NULL"):
            return (left is None) if expr.op == "IS NULL" else (left is not None)
        left, right = _coerce_pair(left, right)
        if expr.op == "=": return left == right
        if expr.op in ("!=", "<>"): return left != right
        if expr.op == "<": return left < right
        if expr.op == "<=": return left <= right
        if expr.op == ">": return left > right
        if expr.op == ">=": return left >= right
        if expr.op == "+": return left + right
        if expr.op == "-": return left - right
        if expr.op == "*": return left * right
        if expr.op == "/": return left / right
        if expr.op == "%": return left % right
        if expr.op == "LIKE":
            import re
            pattern = "^" + re.escape(str(right)).replace(r"\%", ".*").replace(r"\_", ".") + "$"
            return re.match(pattern, str(left), flags=re.DOTALL) is not None
    if isinstance(expr, Function):
        name = expr.name.upper()
        args = [_eval(arg, row) for arg in expr.args]
        if name == "LOWER" and len(args) == 1: return str(args[0]).lower()
        if name == "UPPER" and len(args) == 1: return str(args[0]).upper()
        if name == "ABS" and len(args) == 1: return abs(args[0])
        raise SQLExecutionError(f"unsupported scalar function {name}")
    raise SQLExecutionError(f"unsupported expression: {expr!r}")

AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

def _aggregate(expr: Expr, rows: list[dict[str, Any]]) -> Any:
    if not isinstance(expr, Function) or expr.name.upper() not in AGGREGATES:
        if not rows: return None
        return _eval(expr, rows[0])
    name = expr.name.upper()
    if len(expr.args) != 1:
        raise SQLExecutionError(f"{name} requires exactly one argument")
    arg = expr.args[0]
    values = [1 if isinstance(arg, Star) else _eval(arg, row) for row in rows]
    if name == "COUNT":
        return len(values) if isinstance(arg, Star) else sum(v is not None for v in values)
    values = [v for v in values if v is not None]
    if not values: return None
    if name in ("SUM", "AVG"):
        try:
            values = [float(v) if isinstance(v, str) and "." in v else int(v) if isinstance(v, str) else v for v in values]
        except ValueError as exc:
            raise SQLExecutionError(f"{name} requires numeric values") from exc
    if name == "SUM": return sum(values)
    if name == "AVG": return sum(values) / len(values)
    if name == "MIN": return min(values)
    if name == "MAX": return max(values)
    raise SQLExecutionError(f"unsupported aggregate {name}")

class QueryEngine:
    def __init__(self, data_dir: str = "data", catalog: TableCatalog | None = None):
        self.catalog = catalog or TableCatalog(data_dir)

    def execute(self, sql: str) -> QueryResult:
        started = time.perf_counter()
        query = parse(sql)
        rows = self.catalog.load(query.table.name)
        # Qualify source columns to prevent common collisions in joins, while
        # keeping unqualified names available when unambiguous.
        rows = [{**row, **{f"{query.table.alias or query.table.name}.{k}": v for k, v in row.items()}} for row in rows]
        for join in query.joins:
            right_rows = self.catalog.load(join.table.name)
            right_rows = [{**row, **{f"{join.table.alias or join.table.name}.{k}": v for k, v in row.items()}} for row in right_rows]
            joined = []
            for left_row in rows:
                for right_row in right_rows:
                    combined = dict(left_row)
                    combined.update(right_row)
                    if _eval(Binary(join.left, join.op, join.right), combined):
                        joined.append(combined)
            rows = joined
        if query.where is not None:
            rows = [row for row in rows if bool(_eval(query.where, row))]
        aggregate_query = bool(query.group_by) or any(
            isinstance(item.expr, Function) and item.expr.name.upper() in AGGREGATES
            for item in query.columns
        )
        output: list[tuple[Any, ...]] = []
        if aggregate_query:
            groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
            if query.group_by:
                for row in rows:
                    key = tuple(_eval(expr, row) for expr in query.group_by)
                    groups.setdefault(key, []).append(row)
            else:
                groups[()] = rows
            for _, group_rows in groups.items():
                output.append(tuple(_aggregate(item.expr, group_rows) for item in query.columns))
        else:
            for row in rows:
                output.append(tuple(row.values()) if isinstance(query.columns[0].expr, Star) and len(query.columns) == 1 else tuple(_eval(item.expr, row) for item in query.columns))
        # Column names use aliases, identifiers, function labels, or star expansion.
        columns = []
        for item in query.columns:
            if item.alias:
                columns.append(item.alias)
            elif isinstance(item.expr, Identifier):
                columns.append(item.expr.name)
            elif isinstance(item.expr, Function):
                columns.append(f"{item.expr.name.lower()}({', '.join(getattr(a, 'name', '*') for a in item.expr.args)})")
            elif isinstance(item.expr, Star):
                columns = list(rows[0].keys()) if rows else []
            else:
                columns.append(str(item.expr))
        # ORDER BY expressions resolve against source rows when nonaggregate; aggregate ORDER BY aliases are supported.
        if query.order_by:
            decorated = []
            for outrow in output:
                mapping = {columns[i]: outrow[i] for i in range(min(len(columns), len(outrow)))}
                decorated.append((outrow, mapping))
            for order_item in reversed(query.order_by):
                key_name = order_item.expr.name if isinstance(order_item.expr, Identifier) else None
                # repr() tiebreaker: deterministic total order without ever
                # comparing mixed-type row tuples (TypeError in Python 3).
                decorated.sort(key=lambda pair: (_order_key(pair[1].get(key_name, _safe_eval_order(order_item.expr, pair[1]))), repr(pair[0])), reverse=order_item.descending)
            output = [pair[0] for pair in decorated]
        if query.limit is not None:
            output = output[:query.limit]
        return QueryResult(columns, output, time.perf_counter() - started, format_plan(plan(query)))

def _safe_eval_order(expr: Expr, row: dict[str, Any]) -> Any:
    try: return _eval(expr, row)
    except Exception: return None


def _order_key(value: Any) -> tuple[int, float, str]:
    """Total ordering for ORDER BY.

    CSV storage loads every value as text, so a salary column sorts as
    ("90000" > "130000") without help. Numeric strings compare as numbers;
    genuine strings compare as strings; numbers sort before strings and
    NULLs sort last, keeping the ordering total across mixed types.
    """
    if isinstance(value, bool):
        return (0, float(value), "")
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    if isinstance(value, str):
        try:
            return (0, float(value), "")
        except ValueError:
            return (1, 0.0, value)
    if value is None:
        return (2, 0.0, "")
    return (1, 0.0, str(value))
