"""Talks to mcp_server.py exactly like Claude Code would (over stdio)."""
import asyncio, sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
async def main():
    p = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print([t.name for t in tools.tools])
            for name, args in [("find_symbol", {"name": "send"}),
                               ("who_calls", {"symbol": "send"}),
                               ("who_calls", {"symbol": "Session.send"}),
                               ("what_it_calls", {"symbol": "requests/api.py::get", "depth": 2}),
                               ("get_context", {"symbol": "Session.send"})]:
                res = await s.call_tool(name, args)
                txt = res.content[0].text
                print(f"--- {name} {args}\n{txt[:400]}\n")
asyncio.run(main())

