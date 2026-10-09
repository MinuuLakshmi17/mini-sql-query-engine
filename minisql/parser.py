"""Recursive-descent SQL parser using precedence climbing for expressions."""
from __future__ import annotations
from .ast import (
    Binary, Expr, Function, Identifier, Join, Literal, OrderItem, Select,
    SelectItem, Star, TableRef, Unary,
)
from .tokenizer import SQLSyntaxError, Token, tokenize

PRECEDENCE = {"OR": 1, "AND": 2, "=": 3, "!=": 3, "<>": 3, "<": 3, "<=": 3, ">": 3, ">=": 3, "LIKE": 3, "IS": 3, "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}

class Parser:
    def __init__(self, sql: str):
        self.tokens = tokenize(sql)
        self.i = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        token = self.current
        self.i += 1
        return token

    def match(self, *values: str) -> bool:
        if self.current.value.upper() in values:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        if self.current.value.upper() != value:
            raise SQLSyntaxError(f"expected {value!r} at position {self.current.position}, got {self.current.value!r}")
        return self.advance()

    def identifier(self) -> str:
        if self.current.kind not in ("IDENT",):
            raise SQLSyntaxError(f"expected identifier at position {self.current.position}")
        return self.advance().value

    def parse(self) -> Select:
        self.expect("SELECT")
        columns = [self.select_item()]
        while self.match(","):
            columns.append(self.select_item())
        self.expect("FROM")
        table = self.table_ref()
        joins = []
        while self.match("INNER", "JOIN"):
            # INNER JOIN and JOIN both mean inner join in this subset.
            if self.tokens[self.i - 1].value.upper() == "INNER":
                self.expect("JOIN")
            joined = self.table_ref()
            self.expect("ON")
            left = self.expression(4)
            op = self.current.value
            if op not in ("=", "!=", "<>", "<", "<=", ">", ">="):
                raise SQLSyntaxError(f"unsupported JOIN predicate at position {self.current.position}")
            self.advance()
            right = self.expression(4)
            joins.append(Join(joined, left, op, right))
        where = self.expression() if self.match("WHERE") else None
        group_by = []
        if self.match("GROUP"):
            self.expect("BY")
            group_by.append(self.expression())
            while self.match(","):
                group_by.append(self.expression())
        order_by = []
        if self.match("ORDER"):
            self.expect("BY")
            while True:
                expr = self.expression()
                descending = self.match("DESC")
                if not descending:
                    self.match("ASC")
                order_by.append(OrderItem(expr, descending))
                if not self.match(","):
                    break
        limit = None
        if self.match("LIMIT"):
            token = self.advance()
            if token.kind != "NUMBER" or "." in token.value:
                raise SQLSyntaxError(f"LIMIT requires a non-negative integer at position {token.position}")
            limit = int(token.value)
        self.match(";")
        if self.current.kind != "EOF":
            raise SQLSyntaxError(f"unexpected token {self.current.value!r} at position {self.current.position}")
        return Select(tuple(columns), table, tuple(joins), where, tuple(group_by), tuple(order_by), limit)

    def select_item(self) -> SelectItem:
        expr = self.expression()
        alias = None
        if self.match("AS"):
            alias = self.identifier()
        elif self.current.kind == "IDENT" and self.current.value.upper() not in ("FROM",):
            # SQL's optional bare alias; reserved clause words are tokenized separately.
            alias = self.advance().value
        return SelectItem(expr, alias)

    def table_ref(self) -> TableRef:
        name = self.identifier()
        alias = None
        if self.match("AS"):
            alias = self.identifier()
        elif self.current.kind == "IDENT":
            alias = self.advance().value
        return TableRef(name, alias)

    def expression(self, min_prec: int = 0) -> Expr:
        token = self.advance()
        upper = token.value.upper()
        if token.kind == "NUMBER":
            left: Expr = Literal(float(token.value) if "." in token.value else int(token.value))
        elif token.kind == "STRING":
            left = Literal(token.value)
        elif upper in ("TRUE", "FALSE"):
            left = Literal(upper == "TRUE")
        elif upper == "NULL":
            left = Literal(None)
        elif token.value == "*":
            left = Star()
        elif upper in ("NOT", "+", "-"):
            left = Unary(upper, self.expression(6))
        elif token.value == "(":
            left = self.expression()
            self.expect(")")
        elif token.kind in ("IDENT",):
            name = token.value
            if self.match("("):
                args = []
                if not self.match(")"):
                    args.append(self.expression())
                    while self.match(","):
                        args.append(self.expression())
                    self.expect(")")
                left = Function(name.upper(), tuple(args))
            elif self.match("."):
                if self.match("*"):
                    left = Star()
                else:
                    left = Identifier(name + "." + self.identifier())
            else:
                left = Identifier(name)
        else:
            raise SQLSyntaxError(f"expected expression at position {token.position}, got {token.value!r}")

        while True:
            op = self.current.value.upper()
            if op == "IS":
                prec = PRECEDENCE["IS"]
                if prec < min_prec:
                    break
                self.advance()
                negate = self.match("NOT")
                self.expect("NULL")
                left = Binary(left, "IS NOT NULL" if negate else "IS NULL", Literal(None))
                continue
            prec = PRECEDENCE.get(op, -1)
            if prec < min_prec:
                break
            self.advance()
            right = self.expression(prec + 1)
            left = Binary(left, op, right)
        return left

def parse(sql: str) -> Select:
    return Parser(sql).parse()
