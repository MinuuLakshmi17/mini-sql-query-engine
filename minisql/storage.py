"""CSV and JSON table loading, plus a minimal adapter protocol for custom stores."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any

class TableCatalog:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def register_rows(self, name: str, rows: list[dict[str, Any]]) -> None:
        if not name or not rows and not isinstance(rows, list):
            raise ValueError("invalid table registration")
        self._cache[name.lower()] = [dict(row) for row in rows]

    def load(self, name: str) -> list[dict[str, Any]]:
        key = name.lower()
        if key in self._cache:
            return [dict(row) for row in self._cache[key]]
        csv_path = self.data_dir / f"{name}.csv"
        json_path = self.data_dir / f"{name}.json"
        jsonl_path = self.data_dir / f"{name}.jsonl"
        if csv_path.is_file():
            with csv_path.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        elif json_path.is_file():
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
                raise ValueError(f"{json_path} must contain a JSON array of objects")
            rows = raw
        elif jsonl_path.is_file():
            rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            raise FileNotFoundError(f"no table file for {name!r} in {self.data_dir}")
        self._cache[key] = [dict(row) for row in rows]
        return [dict(row) for row in rows]
