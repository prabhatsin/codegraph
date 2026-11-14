import ast
import json
from pathlib import Path

REPO = Path("../sample_repo/src")

nodes = {}       # id -> node properties
edges = []       # (from_id, relationship, to_id, how)
raw_calls = []   # (function_id, file, class_name, raw_call)
imports = {}     # file -> {local_name: (target_file, name_or_None)}
bases = []       # (class_id, file, raw_base_name)


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


def module_to_file(current_file, level, module):
    parts = Path(current_file).parent.parts if level else ()
    if level > 1:
        parts = parts[: -(level - 1)]
    if module:
        parts = parts + tuple(module.split("."))
    return "/".join(parts) + ".py"


def add_function(fn, rel, src, parent_id, class_name=None):
    name = f"{class_name}.{fn.name}" if class_name else fn.name
    fid = f"{rel}::{name}"
    nodes[fid] = {
        "id": fid, "kind": "Function", "name": fn.name, "file": rel,
        "line": fn.lineno, "code": ast.get_source_segment(src, fn) or "",
        "doc": ast.get_docstring(fn) or "",
    }
    edges.append((parent_id, "CONTAINS", fid, "ast"))
    for c in get_calls(fn):
        raw_calls.append((fid, rel, class_name, c))


# ---------- Pass 1: collect nodes and imports ----------
for path in sorted(REPO.rglob("*.py")):
    rel = str(path.relative_to(REPO))
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    nodes[rel] = {"id": rel, "kind": "File", "name": path.name, "file": rel}
    imports[rel] = {}

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            target = module_to_file(rel, n.level, n.module)
            for a in n.names:
                local = a.asname or a.name
                if n.module is None:  # from . import sessions
                    imports[rel][local] = (module_to_file(rel, n.level, a.name), None)
                else:                 # from .models import Response
                    imports[rel][local] = (target, a.name)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cid = f"{rel}::{node.name}"
            nodes[cid] = {
                "id": cid, "kind": "Class", "name": node.name, "file": rel,
                "line": node.lineno, "code": ast.get_source_segment(src, node) or "",
                "doc": ast.get_docstring(node) or "",
            }
            edges.append((rel, "CONTAINS", cid, "ast"))
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append((cid, rel, b.id))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_overload(item):
                    add_function(item, rel, src, cid, node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_overload(node):
            add_function(node, rel, src, rel)

# names too common to guess (dict.update, file.read, ...)
COMMON = {"update", "read", "write", "get", "items", "keys", "values",
          "copy", "pop", "close", "append", "split", "join", "send"}

# method name -> list of method ids (for the "guess" rule)
methods_by_name = {}
for nid, n in nodes.items():
    if n["kind"] == "Function" and "." in nid.split("::")[1]:
        methods_by_name.setdefault(n["name"], []).append(nid)


# ---------- Pass 2: resolve names to node ids ----------
def resolve_name(name, file):
    if f"{file}::{name}" in nodes:
        return f"{file}::{name}", "local"
    if name in imports[file]:
        mod, real = imports[file][name]
        if real and f"{mod}::{real}" in nodes:
            return f"{mod}::{real}", "import"
    return None, None


def resolve_call(c, file, cls):
    if "." not in c:
        return resolve_name(c, file)
    base, attr = c.split(".", 1)
    if base == "self" and cls and f"{file}::{cls}.{attr}" in nodes:
        return f"{file}::{cls}.{attr}", "self"
    if base in imports[file]:
        mod, real = imports[file][base]
        if real is None and f"{mod}::{attr}" in nodes:
            return f"{mod}::{attr}", "module"
    matches = methods_by_name.get(attr, [])
    if len(matches) == 1 and attr not in COMMON:
        return matches[0], "guess"
    return None, None


for fid, file, cls, c in raw_calls:
    target, how = resolve_call(c, file, cls)
    if target and target != fid:
        edges.append((fid, "CALLS", target, how))

for cid, file, b in bases:
    target, how = resolve_name(b, file)
    if target:
        edges.append((cid, "INHERITS", target, how))

for file, names in imports.items():
    for mod in {m for m, _ in names.values()}:
        if mod in nodes and mod != file:
            edges.append((file, "IMPORTS", mod, "ast"))

edges = sorted(set(edges))

# ---------- Save + summary ----------
Path("graph.json").write_text(json.dumps(
    {"nodes": list(nodes.values()),
     "edges": [{"from": a, "rel": r, "to": b, "how": h} for a, r, b, h in edges]},
    indent=2))

kinds = {}
for n in nodes.values():
    kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
rels = {}
for _, r, _, h in edges:
    rels[f"{r}({h})"] = rels.get(f"{r}({h})", 0) + 1
print("nodes:", kinds)
print("edges:", rels)
print("\nCALLS from api.py:")
for a, r, b, h in edges:
    if r == "CALLS" and a.startswith("requests/api.py"):
        print(f"  {a}  ->  {b}   [{h}]")