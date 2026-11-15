import json

from config import GRAPH
from neo4j import GraphDatabase

TOKEN = "local-development-token-32-bytes"
g = json.load(open(GRAPH))
num = {n["id"]: i + 1 for i, n in enumerate(g["nodes"])}

def chunks(rows, size=1000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]

with GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", TOKEN)) as driver:
    with driver.session(database="default") as s:
        for label in ("File", "Class", "Function"):
            rows = [{"id": num[n["id"]], "key": n["id"], "name": n["name"],
                     "file": n["file"], "line": n.get("line", 0),
                     "code": n.get("code", ""), "doc": n.get("doc", "")}
                    for n in g["nodes"] if n["kind"] == label]
            for batch in chunks(rows):
                s.run(f"UNWIND $rows AS row MERGE (n {{id: row.id}}) "
                      f"SET n:{label}, n.key = row.key, n.name = row.name, "
                      f"n.file = row.file, n.line = row.line, "
                      f"n.code = row.code, n.doc = row.doc", rows=batch).consume()
            print(f"{label}: {len(rows)} nodes")
        for e in g["edges"]:
            s.run(f"MERGE (a {{id: $src}})-[:{e['rel']} {{how: $how}}]->(b {{id: $dst}})",
                  src=num[e["from"]], dst=num[e["to"]], how=e["how"]).consume()
        print(f"edges: {len(g['edges'])}")
