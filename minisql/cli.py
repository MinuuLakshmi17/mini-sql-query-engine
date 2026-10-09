"""CLI for mini-sql."""
from __future__ import annotations
import argparse
import json
from .engine import QueryEngine

def main() -> None:
    parser = argparse.ArgumentParser(description="Execute a supported SQL subset over CSV/JSON files.")
    parser.add_argument("query", help="SQL query, quoted as one shell argument")
    parser.add_argument("--data-dir", default="examples/data", help="directory containing table CSV/JSON files")
    parser.add_argument("--show-plan", action="store_true")
    args = parser.parse_args()
    result = QueryEngine(args.data_dir).execute(args.query)
    print(json.dumps({"columns": result.columns, "rows": result.rows, "elapsed_seconds": result.elapsed_seconds}, default=str, indent=2))
    if args.show_plan:
        print("\nPLAN\n" + result.plan)

if __name__ == "__main__":
    main()
