"""Benchmark: graph context vs BM25 vs vector RAG, scored against the runtime trace."""
import json
import os
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

from config import GRAPH, NAME, SRC, data_file
from context import callees, callers, run

DEPTH = 2
MAX_LINES = 40  # same per-function cap as context()

g = json.load(open(GRAPH))
funcs = {n["id"]: n for n in g["nodes"] if n["kind"] in ("Function", "Class")}
TRUTH = data_file(sys.argv[1] if len(sys.argv) > 1 else "trace_edges.json")
trace = [tuple(e) for e in json.load(open(TRUTH))]
trace = [(a, b) for a, b in trace if a in funcs and b in funcs]  # skip lambdas etc.


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


def embed_all(texts, cache_file=data_file("embeddings.json")):
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

totals = {name: {"recall": 0.0, "tokens": 0, "precision": 0.0, "judged": 0}
          for name in ["graph", *retrievers]}
# Precision can only be judged on functions the tests actually ran: a returned function
# that never ran might be a real but untested caller, so it is left out (not counted wrong).
executed = {k for e in trace for k in e}
for q in questions:
    got = graph_retrieve(q)
    budget = sum(tokens(k) for k in got)
    results = {"graph": got}
    for name, rank in retrievers.items():
        results[name] = fill_budget(rank(q), budget, q["target"])
    for name, got in results.items():
        totals[name]["recall"] += len(set(got) & q["truth"]) / len(q["truth"])
        totals[name]["tokens"] += sum(tokens(k) for k in got)
        judged = set(got) & executed
        if judged:
            totals[name]["precision"] += len(judged & q["truth"]) / len(judged)
            totals[name]["judged"] += 1

n = len(questions)
print(f"repo: {NAME}   truth: {TRUTH}")
print(f"{n} questions ({sum(q['kind'] == 'impact' for q in questions)} impact, "
      f"{sum(q['kind'] == 'depends' for q in questions)} depends), depth {DEPTH}\n")
print(f"{'method':<8} {'recall':>7} {'avg tokens':>11} {'precision':>10} {'F1':>5}")
for name, t in totals.items():
    r = t["recall"] / n
    p = t["precision"] / t["judged"] if t["judged"] else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    print(f"{name:<8} {r:>7.0%} {t['tokens'] // n:>11} {p:>10.0%} {f1:>5.2f}")
print("precision = share of returned functions that are real callers/callees, judged only on\n"
      "functions the tests ran (a lower bound: untested real calls count as unknown, not right)")


# ---------- Experiment 2: tokens needed to find what the graph found ----------
# Flip the question: instead of a fixed budget, let each method keep reading
# until it has found as much of the truth as the graph did. How many tokens
# does that take?
file_tokens = {f: len((SRC / f).read_text()) // 4
               for f in {funcs[k]["file"] for k in funcs}}
corpus = sum(tokens(k) for k in keys)


def tokens_to_match(ranked, q, goal):
    found, used = set(), 0
    for k in ranked:
        if k == q["target"]:
            continue
        used += tokens(k)
        if k in q["truth"]:
            found.add(k)
            if len(found) / len(q["truth"]) >= goal:
                return used
    return corpus  # never got there: it read everything


spend = {name: 0 for name in ["graph", "whole files", *retrievers]}
matched = 0
for q in questions:
    got = graph_retrieve(q)
    goal = len(set(got) & q["truth"]) / len(q["truth"])
    if goal == 0:
        continue
    matched += 1
    spend["graph"] += sum(tokens(k) for k in got)
    # what an agent pays if it opens every file that holds a true answer
    files = {funcs[k]["file"] for k in q["truth"]} | {funcs[q["target"]]["file"]}
    spend["whole files"] += sum(file_tokens[f] for f in files)
    for name, rank in retrievers.items():
        spend[name] += tokens_to_match(rank(q), q, goal)

results = {"repo": NAME, "truth": str(TRUTH), "questions": n, "methods": []}
for name, t in totals.items():
    r = t["recall"] / n
    p = t["precision"] / t["judged"] if t["judged"] else 0.0
    results["methods"].append({"method": name, "recall": round(r, 3), "precision": round(p, 3),
                               "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
                               "tokens_to_match": spend.get(name, 0) // max(matched, 1)})
results["methods"].append({"method": "whole files", "tokens_to_match": spend["whole files"] // max(matched, 1)})
data_file("bench_results.json").write_text(json.dumps(results, indent=2))

print(f"\nTokens needed to find what the graph found ({matched} questions)\n")
print(f"{'method':<12} {'avg tokens':>11} {'vs graph':>9}")
for name, total in spend.items():
    print(f"{name:<12} {total // matched:>11} {total / spend['graph']:>8.1f}x")
