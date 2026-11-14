from neo4j import GraphDatabase

TOKEN = "local-development-token-32-bytes"

with GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", TOKEN)) as driver:
    driver.verify_connectivity()
    with driver.session(database="default") as session:
        session.run("CREATE (a {id: 1})-[:CALLS]->(b {id: 2})").consume()
        row = session.run("MATCH (a {id: 1})-[:CALLS]->(b) RETURN b.id AS id").single()
        print("Got:", row["id"])