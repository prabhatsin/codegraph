import ast
from pathlib import Path

REPO = Path("../sample_repo/src")



def is_overload(fn):
    return any(
        (isinstance(d, ast.Name) and d.id == "overload")
        or (isinstance(d, ast.Attribute) and d.attr == "overload")
        for d in fn.decorator_list
    )


def get_calls(func):
    calls = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute):
                if isinstance(f.value, ast.Name):
                    calls.add(f"{f.value.id}.{f.attr}")
                else:
                    calls.add(f.attr)
    return sorted(calls)


def parse_file(path):
    rel = str(path.relative_to(REPO))
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            print(f"  CLASS    {rel}::{node.name}  (line {node.lineno})")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_overload(item):
                    print(f"  METHOD   {rel}::{node.name}.{item.name}  (line {item.lineno})")
                    print(f"      calls: {get_calls(item)}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_overload(node):
        # elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            print(f"  FUNCTION {rel}::{node.name}  (line {node.lineno})")
            print(f"      calls: {get_calls(node)}")

for path in sorted(REPO.rglob("*.py")):
    print(f"FILE {path.relative_to(REPO)}")
    parse_file(path)