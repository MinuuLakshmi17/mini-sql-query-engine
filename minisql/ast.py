"""SQL abstract syntax tree nodes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Expr:
    pass

@dataclass(frozen=True)
class Identifier(Expr):
    name: str

@dataclass(frozen=True)
class Literal(Expr):
    value: Any

@dataclass(frozen=True)
class Star(Expr):
    pass

@dataclass(frozen=True)
class Unary(Expr):
    op: str
    expr: Expr

@dataclass(frozen=True)
class Binary(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass(frozen=True)
class Function(Expr):
    name: str
    args: tuple[Expr, ...]

@dataclass(frozen=True)
class SelectItem:
    expr: Expr
    alias: str | None = None

@dataclass(frozen=True)
class TableRef:
    name: str
    alias: str | None = None

@dataclass(frozen=True)
class Join:
    table: TableRef
    left: Expr
    op: str
    right: Expr

@dataclass(frozen=True)
class OrderItem:
    expr: Expr
    descending: bool = False

@dataclass(frozen=True)
class Select:
    columns: tuple[SelectItem, ...]
    table: TableRef
    joins: tuple[Join, ...] = ()
    where: Expr | None = None
    group_by: tuple[Expr, ...] = ()
    order_by: tuple[OrderItem, ...] = ()
    limit: int | None = None
