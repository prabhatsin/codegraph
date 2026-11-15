"""CodeGraph command line: works on any Python repo, no code changes needed.

    python codegraph.py index  <repo>    parse the repo and load it into HydraDB
    python codegraph.py learn  <repo>    run its pytest suite, add runtime calls the parser missed
    python codegraph.py serve  <repo>    start the MCP server for coding agents
    python codegraph.py bench  <repo>    retrieval/token benchmark on held-out tests (after learn)
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = {
    "index": ["extract.py", "load.py"],
    "learn": ["trace_pytest.py", "learn.py"],
    "serve": ["mcp_server.py"],
    "bench": [("bench.py", "trace_test.json")],
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in STEPS:
        sys.exit(__doc__)
    command, repo = sys.argv[1], Path(sys.argv[2]).expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"Not a folder: {repo}")
    env = {**os.environ, "CODEGRAPH_REPO": str(repo)}
    for step in STEPS[command]:
        script, *args = step if isinstance(step, tuple) else (step,)
        print(f"\n== {script} {' '.join(args)}  [{repo.name}]", file=sys.stderr, flush=True)
        done = subprocess.run([sys.executable, str(HERE / script), *args], env=env, cwd=HERE)
        if done.returncode:
            sys.exit(done.returncode)


if __name__ == "__main__":
    main()
