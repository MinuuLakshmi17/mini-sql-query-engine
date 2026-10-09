-- Run individual queries through the CLI.
SELECT name, salary FROM employees WHERE salary >= 110000 ORDER BY salary DESC LIMIT 3;
SELECT department_id, COUNT(*) AS headcount, AVG(salary) AS avg_salary
FROM employees GROUP BY department_id ORDER BY department_id;
SELECT employees.name, departments.name AS department
FROM employees INNER JOIN departments ON employees.department_id = departments.id
ORDER BY employees.name;
