from pathlib import Path
import pytest
from minisql import QueryEngine
from minisql.parser import parse
from minisql.tokenizer import SQLSyntaxError
from minisql.storage import TableCatalog

@pytest.fixture
def engine():
    catalog = TableCatalog(".")
    catalog.register_rows("employees", [
        {"id": 1, "name": "Ada", "department_id": 10, "salary": 120000},
        {"id": 2, "name": "Linus", "department_id": 20, "salary": 110000},
        {"id": 3, "name": "Grace", "department_id": 10, "salary": 130000},
        {"id": 4, "name": "Ken", "department_id": 30, "salary": 90000},
    ])
    catalog.register_rows("departments", [
        {"id": 10, "name": "Engineering"},
        {"id": 20, "name": "Research"},
        {"id": 30, "name": "Operations"},
    ])
    return QueryEngine(catalog=catalog)

def test_select_where_order_limit(engine):
    result = engine.execute("SELECT name, salary FROM employees WHERE salary >= 110000 ORDER BY salary DESC LIMIT 2")
    assert result.rows == [("Grace", 130000), ("Ada", 120000)]
    assert result.columns == ["name", "salary"]

def test_group_by_aggregates(engine):
    result = engine.execute("SELECT department_id, COUNT(*) AS n, AVG(salary) AS avg_salary FROM employees GROUP BY department_id ORDER BY department_id")
    assert result.rows == [(10, 2, 125000.0), (20, 1, 110000.0), (30, 1, 90000.0)]

def test_inner_join(engine):
    result = engine.execute("SELECT employees.name, departments.name AS department FROM employees INNER JOIN departments ON employees.department_id = departments.id ORDER BY employees.name")
    assert result.rows == [
        ("Ada", "Engineering"), ("Grace", "Engineering"),
        ("Ken", "Operations"), ("Linus", "Research")
    ]

def test_count_and_empty_aggregate(engine):
    assert engine.execute("SELECT COUNT(*) AS n FROM employees WHERE salary > 999999").rows == [(0,)]

def test_scalar_functions_and_null(engine):
    catalog = TableCatalog(".")
    catalog.register_rows("t", [{"x": "ALPHA", "y": None}, {"x": "Beta", "y": 2}])
    q = QueryEngine(catalog=catalog)
    assert q.execute("SELECT LOWER(x) AS lower_x FROM t ORDER BY lower_x").rows == [("alpha",), ("beta",)]
    assert q.execute("SELECT x FROM t WHERE y IS NULL").rows == [("ALPHA",)]

def test_parser_rejects_trailing_garbage():
    with pytest.raises(SQLSyntaxError):
        parse("SELECT id FROM employees @")

def test_order_by_numeric_strings_from_csv(tmp_path):
    # CSV storage loads everything as text; ORDER BY must still sort
    # numerically ("90000" < "130000"), not lexicographically.
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "staff.csv").write_text("name,salary\nKen,90000\nGrace,130000\nAda,120000\n")
    q = QueryEngine(str(data_dir))
    assert q.execute("SELECT name, salary FROM staff ORDER BY salary DESC").rows == [
        ("Grace", "130000"), ("Ada", "120000"), ("Ken", "90000")]
    assert q.execute("SELECT name FROM staff ORDER BY name ASC").rows == [
        ("Ada",), ("Grace",), ("Ken",)]
