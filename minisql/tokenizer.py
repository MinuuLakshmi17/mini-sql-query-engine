"""A small SQL tokenizer with quoted strings and identifiers."""
from __future__ import annotations
from dataclasses import dataclass

class SQLSyntaxError(ValueError):
    pass

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "ASC", "DESC",
    "LIMIT", "AS", "INNER", "JOIN", "ON", "AND", "OR", "NOT",
    "IS", "NULL", "TRUE", "FALSE", "LIKE",
}

def tokenize(sql: str) -> list[Token]:
    out: list[Token] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        if c == "-" and i + 1 < n and sql[i + 1] == "-":
            end = sql.find("\n", i)
            i = n if end < 0 else end + 1
            continue
        if c in "(),.*+-/%=<>;":
            start = i
            if i + 1 < n and sql[i:i+2] in ("<=", ">=", "!=", "<>"):
                out.append(Token("OP", sql[i:i+2], i)); i += 2
            else:
                kind = "PUNCT" if c in "(),.;" else ("OP" if c in "=<>+-/%" else "PUNCT")
                out.append(Token(kind, c, start)); i += 1
            continue
        if c == "'":
            start = i; i += 1; chars = []
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        chars.append("'"); i += 2; continue
                    i += 1; break
                chars.append(sql[i]); i += 1
            else:
                raise SQLSyntaxError(f"unterminated string literal at position {start}")
            out.append(Token("STRING", "".join(chars), start))
            continue
        if c == '"':
            start = i; i += 1; chars = []
            while i < n:
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        chars.append('"'); i += 2; continue
                    i += 1; break
                chars.append(sql[i]); i += 1
            else:
                raise SQLSyntaxError(f"unterminated quoted identifier at position {start}")
            out.append(Token("IDENT", "".join(chars), start))
            continue
        if c.isdigit():
            start = i; i += 1
            while i < n and (sql[i].isdigit() or sql[i] == "."):
                i += 1
            raw = sql[start:i]
            if raw.count(".") > 1:
                raise SQLSyntaxError(f"invalid number {raw!r} at position {start}")
            out.append(Token("NUMBER", raw, start))
            continue
        if c.isalpha() or c == "_":
            start = i; i += 1
            while i < n and (sql[i].isalnum() or sql[i] in "_$"):
                i += 1
            value = sql[start:i]
            out.append(Token("KEYWORD" if value.upper() in KEYWORDS else "IDENT", value, start))
            continue
        raise SQLSyntaxError(f"unexpected character {c!r} at position {i}")
    out.append(Token("EOF", "", n))
    return out
