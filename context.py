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

def callers(node_id, depth=2):
    """Who calls this, up to `depth` hops back -> 'what breaks if I change it?'"""
    return run(f"MATCH (a {{id: $id}})<-[:CALLS*1..{int(depth)}]-(b) "
               "RETURN DISTINCT b.id AS id, b.key AS key", id=node_id)


def callees(node_id, depth=2):
    """What this calls, up to `depth` hops forward -> 'what does it depend on?'"""
    return run(f"MATCH (a {{id: $id}})-[:CALLS*1..{int(depth)}]->(b) "
               "RETURN DISTINCT b.id AS id, b.key AS key", id=node_id)


if __name__ == "__main__":
    target = [r for r in find("send") if r["key"].endswith("Session.send")][0]
    print("Callers of Session.send (2 hops):")
    for r in callers(target["id"]):
        print("  ", r["key"])