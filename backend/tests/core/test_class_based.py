import ast
from pathlib import Path

import erp

SOURCE_ROOT = Path(erp.__file__).parent


def test_application_code_has_no_module_level_functions():
    offenders = []
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                offenders.append(f"{path.relative_to(SOURCE_ROOT)}:{node.name}")
    assert offenders == []
