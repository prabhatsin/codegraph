"""CodeGraph MCP server: gives coding agents graph-walked context from HydraDB."""
from mcp.server import MCPServer

from context import callees, callers, context, find, run

mcp = MCPServer(
    "codegraph",
    instructions=(
        "Code context from a call graph stored in HydraDB. Prefer these tools over "
        "grepping or reading whole files: find_symbol to locate code, who_calls for "
        "'what breaks if I change X', what_it_calls for dependencies, and get_context "
        "for the code of a function plus its callers and callees."
    ),
)


def resolve(symbol):
    """'Session.send' or 'requests/sessions.py::Session.send' -> (id, key) or an error text."""
    if "::" in symbol:
        rows = run("MATCH (n {key: $k}) RETURN n.id AS id, n.key AS key", k=symbol)
    else:
        name = symbol.split(".")[-1]
        rows = [r for r in find(name) if r["key"].endswith("::" + symbol)
                or r["key"].endswith("." + symbol) or symbol == name]
    if len(rows) == 1:
        return rows[0]["id"], rows[0]["key"]
    if not rows:
        return None, f"No function or class named '{symbol}'. Try find_symbol."
    options = "\n".join(f"  {r['key']}" for r in rows)
    return None, f"'{symbol}' is ambiguous. Call again with one of:\n{options}"


def listing(title, found):
    if not found:
        return f"{title}: none found"
    rows = sorted(found.items(), key=lambda x: (x[1]["hops"], x[0]))
    return title + ":\n" + "\n".join(
        f"  {n['hops']} hop  {k}  (line {n['line']})" for k, n in rows)


@mcp.tool()
def find_symbol(name: str) -> str:
    """Find every function or class with this name, e.g. 'send'. Returns full keys
    like 'requests/sessions.py::Session.send' with line numbers."""
    rows = find(name.split(".")[-1])
    if not rows:
        return f"No function or class named '{name}'."
    return "\n".join(f"{r['key']}  (line {r['line']})" for r in rows)


@mcp.tool()
def who_calls(symbol: str, depth: int = 2) -> str:
    """What breaks if I change this? Lists every function that calls `symbol`,
    directly or up to `depth` hops back. `symbol` is a name like 'Session.send'
    or a full key from find_symbol."""
    node_id, key = resolve(symbol)
    if node_id is None:
        return key
    return listing(f"Callers of {key}", callers(node_id, depth))


@mcp.tool()
def what_it_calls(symbol: str, depth: int = 2) -> str:
    """What does this depend on? Lists every function `symbol` calls, directly or
    up to `depth` hops forward."""
    node_id, key = resolve(symbol)
    if node_id is None:
        return key
    return listing(f"Callees of {key}", callees(node_id, depth))


@mcp.tool()
def get_context(symbol: str, depth: int = 1) -> str:
    """The source code of `symbol` plus the code of its callers and callees, in one
    compact block. Use this instead of opening whole files."""
    node_id, key = resolve(symbol)
    if node_id is None:
        return key
    return context(node_id, depth)


if __name__ == "__main__":
    mcp.run()  # stdio, which is what Claude Code and Cursor use