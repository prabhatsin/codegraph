"""Which codebase CodeGraph works on. Nothing here is specific to one repo:
point it at any Python project with  CODEGRAPH_REPO=/path/to/repo  (codegraph.py sets this).

Auto-detection:
  * source folder = <repo>/src if it exists, else <repo>
  * packages      = folders in it that contain __init__.py, minus tests/docs/examples/...
  * data folder   = data/<package name>  (or data/<repo folder name> if several packages)
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

SKIP = {"tests", "test", "testing", "docs", "doc", "examples", "example",
        "benchmarks", "benchmark", "scripts", "tools", "build", "dist"}

REPO_ROOT = Path(os.environ.get("CODEGRAPH_REPO", "../sample_repo")).resolve()
SRC = REPO_ROOT / "src" if (REPO_ROOT / "src").is_dir() else REPO_ROOT
PACKAGES = sorted(d.name for d in SRC.iterdir()
                  if d.is_dir() and (d / "__init__.py").exists() and d.name not in SKIP)
if not PACKAGES:
    raise SystemExit(f"No Python package (folder with __init__.py) found in {SRC}")
PKG_DIRS = [SRC / p for p in PACKAGES]
NAME = PACKAGES[0] if len(PACKAGES) == 1 else REPO_ROOT.name

DATA = Path(__file__).resolve().parent / "data" / NAME
DATA.mkdir(parents=True, exist_ok=True)
GRAPH = DATA / "graph.json"


def data_file(name):
    """'trace_test.json' -> DATA/trace_test.json (a path with a folder is used as given)."""
    p = Path(name)
    return p if p.parent != Path(".") else DATA / p
