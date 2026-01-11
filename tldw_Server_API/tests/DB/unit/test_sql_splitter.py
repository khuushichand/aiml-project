from tldw_Server_API.app.core.DB_Management.sql_utils import split_sql_statements


def test_split_simple_statements():
    sql = "CREATE TABLE a(id int); CREATE TABLE b(id int);"
    statements = split_sql_statements(sql)
    assert statements == ["CREATE TABLE a(id int)", "CREATE TABLE b(id int)"]


def test_split_dollar_quoted_function():
    sql = """
    CREATE TABLE a(id int);
    CREATE OR REPLACE FUNCTION foo()
    RETURNS trigger AS $$
    BEGIN
      PERFORM 1;
      IF TG_OP = 'INSERT' THEN
        RETURN NEW;
      END IF;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TABLE b(id int);
    """
    statements = split_sql_statements(sql)
    assert len(statements) == 3
    assert statements[1].startswith("CREATE OR REPLACE FUNCTION foo()")
    assert "$$ LANGUAGE plpgsql" in statements[1]


def test_split_ignores_semicolons_in_comments():
    sql = "CREATE TABLE a(id int); -- comment; still comment\nCREATE TABLE b(id int);"
    statements = split_sql_statements(sql)
    assert statements == ["CREATE TABLE a(id int)", "CREATE TABLE b(id int)"]
