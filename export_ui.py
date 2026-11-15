"""Export the graph from HydraDB for the UI (ui/index.html works offline, no server).

    python export_ui.py ../rich_repo        -> ../Frontend/static/data.js

For every function and class it walks callers and callees (2 hops) with algo.SSpaths,
exactly what the agent tools do, and saves who is reached, by which edges, and the code.
"""
import json
import os
import sys
from pathlib import Path

if len(sys.argv) > 1:
    os.environ["CODEGRAPH_REPO"] = sys.argv[1]

from config import GRAPH, NAME, SRC  # noqa: E402
from context import driver, run      # noqa: E402

DEPTH, MAX_LINES = 2, 40
HOW = ["self", "local", "import", "module", "init", "override", "super", "property",
       "guess", "runtime"]

g = json.load(open(GRAPH))
items = [n for n in g["nodes"] if n["kind"] in ("Function", "Class")]
index = {n["id"]: i for i, n in enumerate(items)}


def snippet(code):
    lines = code.splitlines()
    return "\n".join(lines[:MAX_LINES]) + (f"\n    # ... {len(lines) - MAX_LINES} more lines"
                                            if len(lines) > MAX_LINES else "")


nodes = []
for n in items:
    code = snippet(n["code"])
    nodes.append([n["id"], n["kind"][0], n["file"], n["line"],
                  n["line"] + len(n["code"].splitlines()) - 1, len(code) // 4, code])

files = {}
for f in sorted({n["file"] for n in items}):
    text = (SRC / f).read_text(encoding="utf-8")
    files[f] = [len(text) // 4, len(text.splitlines())]

ids = {r["key"]: r["id"] for r in run("MATCH (n:Function) RETURN n.key AS key, n.id AS id")}
ids.update({r["key"]: r["id"] for r in run("MATCH (n:Class) RETURN n.key AS key, n.id AS id")})

Q = ("CALL algo.SSpaths({sourceNode: $id, relTypes: ['CALLS'], relDirection: $dir, "
     f"maxLen: {DEPTH}, pathCount: 500}}) YIELD path RETURN path")
walks = {}
with driver.session(database="default") as s:
    for i, n in enumerate(items):
        entry = {}
        for name, direction in (("in", "incoming"), ("out", "outgoing")):
            reach, edges = {}, set()
            for r in s.run(Q, id=ids[n["id"]], dir=direction):
                p = r["path"]
                ks = [index.get(x["key"]) for x in p.nodes]
                if None in ks:
                    continue
                for hop, k in enumerate(ks[1:], 1):
                    reach[k] = min(hop, reach.get(k, 9))
                for a, b, rel in zip(ks, ks[1:], p.relationships):
                    how = HOW.index(rel.get("how", "guess"))
                    edges.add((b, a, how) if direction == "incoming" else (a, b, how))
            if reach:
                entry[name] = [sorted(reach.items()), sorted(edges)]
        if entry:
            walks[i] = entry
        if i % 200 == 0:
            print(f"  {i}/{len(items)}", flush=True)

from config import DATA  # noqa: E402
summary_file = DATA / "summary.json"
summary = json.loads(summary_file.read_text()) if summary_file.exists() else {}
data = {"repo": NAME, "how": HOW, "nodes": nodes, "files": files, "walks": walks,
        "summary": summary}
out = Path(__file__).resolve().parent.parent / "Frontend" / "static" / "data.js"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("window.CODEGRAPH = " + json.dumps(data, separators=(",", ":")) + ";\n")
print(f"{out}: {len(nodes)} symbols, {len(walks)} with callers/callees, "
      f"{out.stat().st_size // 1024} KB")
