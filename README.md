# mini-sql-query-engine

A compact educational SQL engine with its own tokenizer, recursive-descent parser, AST, logical/physical-plan representation, and executor over CSV/JSON tables.

**Honest scope:** this is a deliberately small SQL subset, not a PostgreSQL replacement. It currently supports `SELECT`, `WHERE`, `INNER JOIN`, `GROUP BY`, `ORDER BY`, `LIMIT`, arithmetic/comparison/boolean expressions, `IS NULL`, scalar functions (`LOWER`, `UPPER`, `ABS`), and aggregates (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`). It does not yet integrate directly with `stonebridge`; the storage catalog is isolated behind a small interface so an adapter can be added without coupling the parser/executor to a specific storage implementation.

## Quick start

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

Run a query:
```bash
mini-sql-query-engine "SELECT name, salary FROM employees WHERE salary >= 110000 ORDER BY salary DESC LIMIT 3" --data-dir examples/data --show-plan
```
Or without installing the entry point:
```bash
python -m minisql.cli "SELECT name, salary FROM employees" --data-dir examples/data
```

## Example queries

```sql
SELECT name, salary
FROM employees
WHERE salary >= 110000
ORDER BY salary DESC
LIMIT 3;

SELECT department_id, COUNT(*) AS headcount, AVG(salary) AS avg_salary
FROM employees
GROUP BY department_id
ORDER BY department_id;

SELECT employees.name, departments.name AS department
FROM employees
INNER JOIN departments ON employees.department_id = departments.id
ORDER BY employees.name;
```

## Architecture

```text
SQL text
  -> tokenizer
  -> recursive-descent parser
  -> AST
  -> plan tree
  -> table scan -> nested-loop inner join -> filter
  -> hash-based GROUP BY aggregation -> sort -> limit
  -> rows + elapsed time + plan
```

The current plan tree describes operations, but the executor is still a direct interpreter over the AST for several stages. Predicate pushdown and cost-based physical optimization are roadmap items, not completed features. Joins currently use a nested-loop algorithm.

## Data formats

- CSV: first row is a header; values are initially strings and numeric comparison coercion is conservative.
- JSON: an array of objects.
- JSONL: one JSON object per line.

Put files under `--data-dir` with the table name as the filename, e.g. `employees.csv`.

## Supported expression subset

- Literals: integers, decimals, quoted strings, `NULL`, `TRUE`, `FALSE`
- Column references: `column`, `table.column`
- Comparisons: `=`, `!=`, `<>`, `<`, `<=`, `>`, `>=`, `LIKE`
- Boolean: `AND`, `OR`, `NOT`
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Null checks: `IS NULL`, `IS NOT NULL`
- Scalar functions: `LOWER`, `UPPER`, `ABS`
- Aggregates: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`

## Verification

Tests cover filtering, ordering, limiting, grouped aggregates, inner joins, empty `COUNT(*)`, scalar functions, null checks, and parser rejection of trailing garbage.

For stronger differential validation, add optional SQLite golden tests that execute each supported query against identical data in SQLite and compare normalized result rows. This is not currently a runtime dependency, and the existing suite does not claim exhaustive SQL conformance.

Latency is returned per query as `elapsed_seconds`. For credible benchmark results, generate larger deterministic tables, warm up the engine, repeat each query, and report median/p95 with Python version, CPU, row counts, and query shape. No performance numbers are preclaimed.

## Storage backend integration roadmap

1. Define a `TableStorage` protocol for scan/lookup and schema access.
2. Implement `StonebridgeCatalog` as an adapter to the existing `stonebridge` HTTP or native API, after confirming its exact interface.
3. Add persistence/crash-recovery tests through the adapter.
4. Add predicate pushdown where the storage API can safely evaluate filters.
5. Add hash join, column projection, EXPLAIN output, and a simple cost model.

## Known limitations

- No SQL transactions, indexes, subqueries, outer joins, or DDL.
- No full SQL three-valued logic for `NULL`.
- No cost-based optimizer; predicate pushdown is not implemented.
- `ORDER BY` supports output aliases and projected columns best; arbitrary expressions and mixed-type ordering have limitations.
- No direct `stonebridge` integration yet.
- Not yet benchmarked against SQLite; SQLite comparison is the next validation step.

These limits are documented intentionally: a systems portfolio should distinguish implemented functionality from planned work.
