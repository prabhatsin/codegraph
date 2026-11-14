"""Benchmark: graph context vs BM25 vs vector RAG, scored against the runtime trace."""
import json
import os
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

from context import callees, callers, run
from dotenv import load_dotenv
load_dotenv(override=True)

DEPTH = 2
MAX_LINES = 40  # same per-function cap as context()

g = json.load(open("graph.json"))
funcs = {n["id"]: n for n in g["nodes"] if n["kind"] in ("Function", "Class")}

TRUTH = sys.argv[1] if len(sys.argv) > 1 else "trace_edges.json"
trace = [tuple(e) for e in json.load(open(TRUTH))]



def tokens(key):
    code = "\n".join(funcs[key]["code"].splitlines()[:MAX_LINES])
    return len(code) // 4


# ---------- ground truth from the trace ----------
def reach(start, edges, depth):
    seen, front = set(), {start}
    for _ in range(depth):
        front = {b for a, b in edges if a in front} - seen - {start}
        seen |= front
    return seen


fwd = trace
rev = [(b, a) for a, b in trace]
questions = []
for key in sorted({k for e in trace for k in e}):
    name = key.split("::")[1]
    for kind, edges, text in (
        ("impact", rev, f"Which functions call {name}, directly or indirectly? "
                        f"What would break if I change {name}?"),
        ("depends", fwd, f"What does {name} call? Which functions does {name} depend on?"),
    ):
        truth = reach(key, edges, DEPTH)
        if len(truth) >= 2:
            questions.append({"target": key, "kind": kind, "text": text, "truth": truth})


# ---------- retriever 1: the graph (HydraDB) ----------
def graph_retrieve(q):
    node_id = run("MATCH (n {key: $k}) RETURN n.id AS id", k=q["target"])[0]["id"]
    walk = callers if q["kind"] == "impact" else callees
    return list(walk(node_id, DEPTH).keys())


# ---------- baselines: rank every function, fill the same token budget ----------
keys = list(funcs)
docs = [f"{k}\n{funcs[k]['code']}" for k in keys]


def words(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [w for w in re.split(r"[^A-Za-z0-9]+", text.lower()) if w]


bm25 = BM25Okapi([words(d) for d in docs])


def bm25_rank(q):
    scores = bm25.get_scores(words(q["text"]))
    return [k for _, k in sorted(zip(scores, keys), reverse=True)]


def embed_all(texts, cache_file="embeddings.json"):
    """Gemini embeddings, 50 per request, cached on disk so we pay once."""
    from google import genai
    cache = Path(cache_file)
    vecs = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [t for t in dict.fromkeys(texts) if t not in vecs]
    if todo:
        client = genai.Client()  # reads GEMINI_API_KEY from the environment
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            res = client.models.embed_content(model="gemini-embedding-001",
                                              contents=[t[:8000] for t in batch])
            vecs.update({t: e.values for t, e in zip(batch, res.embeddings)})
        cache.write_text(json.dumps(vecs))
    return vecs


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / ((sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5))


def make_vector_rank():
    vecs = embed_all(docs + [q["text"] for q in questions])

    def rank(q):
        qv = vecs[q["text"]]
        return sorted(keys, key=lambda k: cosine(qv, vecs[docs[keys.index(k)]]), reverse=True)
    return rank


def fill_budget(ranked, budget, target):
    picked, used = [], 0
    for k in ranked:
        if k == target:
            continue
        if used + tokens(k) > budget:
            break
        picked.append(k)
        used += tokens(k)
    return picked


# ---------- run ----------
retrievers = {"bm25": bm25_rank}
if os.environ.get("GEMINI_API_KEY"):
    retrievers["vector"] = make_vector_rank()
else:
    print("GEMINI_API_KEY not set -> skipping the vector baseline\n", file=sys.stderr)

totals = {name: {"recall": 0.0, "tokens": 0} for name in ["graph", *retrievers]}
for q in questions:
    got = graph_retrieve(q)
    budget = sum(tokens(k) for k in got)
    results = {"graph": got}
    for name, rank in retrievers.items():
        results[name] = fill_budget(rank(q), budget, q["target"])
    for name, got in results.items():
        totals[name]["recall"] += len(set(got) & q["truth"]) / len(q["truth"])
        totals[name]["tokens"] += sum(tokens(k) for k in got)

n = len(questions)
print(f"{n} questions ({sum(q['kind'] == 'impact' for q in questions)} impact, "
      f"{sum(q['kind'] == 'depends' for q in questions)} depends), depth {DEPTH}\n")
print(f"{'method':<8} {'recall':>7} {'avg tokens':>11}")
for name, t in totals.items():
    print(f"{name:<8} {t['recall'] / n:>7.0%} {t['tokens'] // n:>11}")


