from neo4j import GraphDatabase

TOKEN = "local-development-token-32-bytes"
driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", TOKEN))


def run(query, **params):
    with driver.session(database="default") as s:
        return [r.data() for r in s.run(query, **params)]


def find(name):
    """All functions and classes with this name -> where they live."""
    rows = []
    for label in ("Function", "Class"):
        rows += run(f"MATCH (n:{label} {{name: $name}}) "
                    "RETURN n.id AS id, n.key AS key, n.line AS line",
                    name=name)
    return rows

def walk(node_id, direction, depth=2, limit=500):
    """Walk CALLS edges inside HydraDB (algo.SSpaths) -> {key: hops away}."""
    q = ("CALL algo.SSpaths({sourceNode: $id, relTypes: ['CALLS'], "
         f"relDirection: '{direction}', maxLen: {int(depth)}, pathCount: {int(limit)}}}) "
         "YIELD path RETURN path")
    found = {}
    with driver.session(database="default") as s:
        for r in s.run(q, id=node_id):

            nodes = r["path"].nodes
            n, hops = nodes[-1], len(nodes) - 1
            if hops and (n["key"] not in found or hops < found[n["key"]]["hops"]):
                found[n["key"]] = {"hops": hops, "line": n["line"], "code": n["code"]}
    return found


def callers(node_id, depth=2):
    """Who calls this -> 'what breaks if I change it?'"""
    return walk(node_id, "incoming", depth)


def callees(node_id, depth=2):
    """What this calls -> 'what does it depend on?'"""
    return walk(node_id, "outgoing", depth)


def snippet(code, max_lines):
    lines = code.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"    # ... {len(lines) - max_lines} more lines"]
    return "\n".join(lines)

def context(node_id, depth=2, max_lines=40):
    """Target + its callers + its callees, as one compact text block for an LLM."""
    t = run("MATCH (n {id: $id}) RETURN n.key AS key, n.line AS line, n.code AS code",
            id=node_id)[0]
    parts = [f"### TARGET {t['key']} (line {t['line']})\n{snippet(t['code'], max_lines)}"]
    for role, found in (("CALLER", callers(node_id, depth)), ("CALLEE", callees(node_id, depth))):
        for key, n in sorted(found.items(), key=lambda x: x[1]["hops"]):
            parts.append(f"### {role} {n['hops']} hop: {key} (line {n['line']})\n"
                         f"{snippet(n['code'], max_lines)}")
    return "\n\n".join(parts)



if __name__ == "__main__":
    from pathlib import Path

    target = [r for r in find("send") if r["key"].endswith("Session.send")][0]
    block = context(target["id"])
    print(block[:1200])
    print("...")

    # Compare: what an agent would read without the graph (every file involved)
    files = {line.split()[-3].split("::")[0] for line in block.splitlines()
             if line.startswith("### ")}
    whole = sum(len((Path("../sample_repo/src") / f).read_text()) for f in files)
    print(f"graph context : {len(block):>6} chars  ~{len(block) // 4} tokens")
    print(f"whole files   : {whole:>6} chars  ~{whole // 4} tokens  {sorted(files)}")