from importlib import import_module


def test_text2sql_module_imports():
    mod = import_module("tldw_Server_API.app.core.Text2SQL")
    assert mod is not None
