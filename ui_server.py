"""Live CodeGraph UI: every click is a real HydraDB traversal.

    python ui_server.py ../rich_repo          then open http://localhost:8765
    (serves the pages in ../Frontend: index.html = live app, static/ = offline page)

Endpoints (JSON):
  /api/repo                      repo name, live graph stats, files, symbols, benchmark summary
  /api/walk?symbol=&dir=in|out&depth=1|2   callers/callees via algo.SSpaths, tokens, query time
  /api/find?q=                   symbol search
  /api/agent_runs                Claude Code benchmark runs (results/<repo>/agent_bench.json)
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if len(sys.argv) > 1:
    os.environ["CODEGRAPH_REPO"] = sys.argv[1]

from config import DATA, GRAPH, NAME, SRC  # noqa: E402
from context import driver, run            # noqa: E402

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("CODEGRAPH_UI_PORT", "8765"))
# the web pages live in their own folder, next to codegraph/ (override with CODEGRAPH_FRONTEND)
FRONTEND = Path(os.environ.get("CODEGRAPH_FRONTEND", HERE.parent / "Frontend")).resolve()
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
         ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png"}
MAX_LINES = 40

graph = json.load(open(GRAPH))
SYMBOLS = {n["id"]: n for n in graph["nodes"] if n["kind"] in ("Function", "Class")}
FILES = {}
for f in sorted({n["file"] for n in SYMBOLS.values()}):
    text = (SRC / f).read_text(encoding="utf-8")
    FILES[f] = [len(text) // 4, len(text.splitlines())]


def snippet(code):
    lines = code.splitlines()
    more = f"\n    # ... {len(lines) - MAX_LINES} more lines" if len(lines) > MAX_LINES else ""
    return "\n".join(lines[:MAX_LINES]) + more


def info(key, hops=0):
    n = SYMBOLS[key]
    code = snippet(n["code"])
    return {"key": key, "kind": n["kind"], "file": n["file"], "line": n["line"],
            "end": n["line"] + len(n["code"].splitlines()) - 1,
            "tokens": len(code) // 4, "hops": hops, "code": code}


def resolve(symbol):
    if symbol in SYMBOLS:
        return symbol
    short = [k for k in SYMBOLS if k.split("::")[1] == symbol]
    tail = [k for k in SYMBOLS if k.split("::")[1].endswith("." + symbol)]
    return (short or tail or [None])[0]


def walk(symbol, direction, depth):
    key = resolve(symbol)
    if not key:
        return {"error": f"No function or class named '{symbol}'"}
    t0 = time.perf_counter()
    node_id = run("MATCH (n {key: $k}) RETURN n.id AS id", k=key)[0]["id"]
    q = ("CALL algo.SSpaths({sourceNode: $id, relTypes: ['CALLS'], relDirection: $dir, "
         f"maxLen: {int(depth)}, pathCount: 500}}) YIELD path RETURN path")
    reach, edges = {}, set()
    with driver.session(database="default") as s:
        for r in s.run(q, id=node_id, dir="incoming" if direction == "in" else "outgoing"):
            p = r["path"]
            ks = [x["key"] for x in p.nodes]
            if any(k not in SYMBOLS for k in ks):
                continue
            for hop, k in enumerate(ks[1:], 1):
                reach[k] = min(hop, reach.get(k, 9))
            for a, b, rel in zip(ks, ks[1:], p.relationships):
                how = rel.get("how", "guess")
                edges.add((b, a, how) if direction == "in" else (a, b, how))
    ms = round((time.perf_counter() - t0) * 1000)
    target = info(key)
    reached = sorted((info(k, h) for k, h in reach.items()), key=lambda x: (x["hops"], x["key"]))
    sent = [target, *reached]
    opened = sorted({x["file"] for x in sent})
    graph_tok = sum(x["tokens"] for x in sent)
    file_tok = sum(FILES[f][0] for f in opened)
    return {"target": target, "reached": reached,
            "edges": [{"from": a, "to": b, "how": h} for a, b, h in sorted(edges)],
            "tokens": {"graph": graph_tok, "files": file_tok, "files_opened": opened,
                       "ratio": round(file_tok / max(graph_tok, 1), 1)},
            "query_ms": ms}


def repo():
    stats = {
        "functions": run("MATCH (n:Function) RETURN count(*) AS c")[0]["c"],
        "classes": run("MATCH (n:Class) RETURN count(*) AS c")[0]["c"],
        "files": run("MATCH (n:File) RETURN count(*) AS c")[0]["c"],
        "calls": run("MATCH ()-[r:CALLS]->() RETURN count(*) AS c")[0]["c"],
        "learned": run("MATCH (a)-[r:CALLS {how: 'runtime'}]->(b) RETURN count(*) AS c")[0]["c"],
    }
    def load(p):
        return json.loads(p.read_text()) if p.exists() else None
    return {"repo": NAME, "stats": stats, "files": FILES,
            "symbols": [{"key": k, "kind": n["kind"], "file": n["file"], "line": n["line"]}
                        for k, n in SYMBOLS.items()],
            "summary": load(DATA / "summary.json"),
            "bench": load(DATA / "bench_results.json")}


def find(q):
    q = q.lower()
    hits = [k for k in SYMBOLS if q in k.split("::")[1].lower()]
    hits.sort(key=lambda k: (not k.split("::")[1].lower().endswith(q), len(k)))
    return [{"key": k, "file": SYMBOLS[k]["file"], "line": SYMBOLS[k]["line"]} for k in hits[:20]]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        qs = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if not url.path.startswith("/api/"):          # pages and assets from Frontend/
                f = (FRONTEND / url.path.lstrip("/")).resolve()
                if f.is_dir():
                    f = f / "index.html"
                if (f == FRONTEND or FRONTEND in f.parents) and f.is_file():
                    return self.send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
                return self.send(404, {"error": f"not found: {url.path}"})
            if url.path == "/api/repo":
                return self.send(200, repo())
            if url.path == "/api/walk":
                return self.send(200, walk(qs.get("symbol", ""), qs.get("dir", "in"),
                                           max(1, min(int(qs.get("depth", 2)), 3))))
            if url.path == "/api/find":
                return self.send(200, find(qs.get("q", "")))
            if url.path == "/api/agent_runs":
                p = HERE / "results" / NAME / "agent_bench.json"
                return self.send(200, json.loads(p.read_text()) if p.exists() else [])
            self.send(404, {"error": "not found"})
        except Exception as e:  # surface HydraDB problems to the page
            self.send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"CodeGraph UI for '{NAME}' on http://localhost:{PORT}  (pages from {FRONTEND})")
    host = os.environ.get("CODEGRAPH_UI_HOST", "127.0.0.1")   # 0.0.0.0 when deployed
    ThreadingHTTPServer((host, PORT), Handler).serve_forever()
