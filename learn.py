"""The graph improves itself: add calls seen at runtime that static parsing missed."""
import json
import sys

from config import data_file
from context import run

TRACE = data_file(sys.argv[1] if len(sys.argv) > 1 else "trace_train.json")
edges = [tuple(e) for e in json.load(open(TRACE))]

ids = {}


def node_id(key):
    if key not in ids:
        rows = run("MATCH (n {key: $k}) RETURN n.id AS id", k=key)
        ids[key] = rows[0]["id"] if rows else None
    return ids[key]


added = known = 0
for caller, callee in edges:
    a, b = node_id(caller), node_id(callee)
    if a is None or b is None:
        continue
    exists = run("MATCH (a {id: $a})-[:CALLS]->(b {id: $b}) RETURN count(*) AS c",
                 a=a, b=b)[0]["c"]
    if exists:
        known += 1
        continue
    run("MERGE (a {id: $a})-[:CALLS {how: 'runtime'}]->(b {id: $b})", a=a, b=b)
    added += 1
    print(f"  + {caller.split('::')[1]} -> {callee.split('::')[1]}")

print(f"\n{TRACE}: {known} calls already in the graph, {added} learned from runtime")
