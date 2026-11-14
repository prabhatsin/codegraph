# CodeGraph

**A context layer for coding agents. It walks a codebase's call graph in HydraDB, so agents get exactly the code they need instead of burning tokens on whole files.**

Built for the HydraDB 48-hour hackathon, Track 2: *the context layer for agents, traversing structure instead of burning tokens.*

---

## The problem

Ask a coding agent "what breaks if I change `Session.send`?" and it has two options:

- **grep and read files.** That costs tokens and turns, and it can't see calls that never write the function's name (`headers["X"] = ...` runs `__setitem__`; `adapter.send()` runs `HTTPAdapter.send`).
- **Vector RAG.** That finds code that *looks like* the question. "Who calls X" is a question about structure, though, and similar-looking text tells you nothing about what calls what.

CodeGraph answers these questions by **walking edges in a graph database**: one query, the exact set of functions, only their code.

## Results

All numbers come from the [`requests`](https://github.com/psf/requests) codebase (19 files, 46 classes, 237 functions). They can be reproduced with the scripts in this repo.

Ground truth for results 1–3 comes from a **runtime trace**: we run real `requests` code and record every function call it makes. The questions are "what breaks if I change X?" and "what does X depend on?", within 2 hops (118 questions on held-out runs).

### 1. Tokens: about 10× fewer for the same answers

How many tokens does each method have to read to find what the graph found? The baselines keep reading their ranked results until they reach the graph's recall. A method that never gets there is charged for the whole codebase.

| Method | Avg tokens | vs CodeGraph |
|---|---|---|
| **CodeGraph (HydraDB)** | **1,601** | **1.0×** |
| Vector RAG (Gemini embeddings) | 14,960 | 9.3× |
| Open every relevant file (grep + read) | 16,813 | 10.5× |
| BM25 (keyword) | 19,018 | 11.9× |

**To reach the same answers, an agent reading whole files burns about 10× more tokens, and vector RAG about 9× more.**

### 2. Retrieval: graph vs vector vs BM25, at the same token budget

The same comparison from the other side: each baseline gets **exactly the token budget the graph used**, and we measure how much of the truth it finds. These numbers are for the full trace, before learning.

| Method | Recall | Avg tokens |
|---|---|---|
| **CodeGraph (HydraDB)** | **75%** | 1,270 |
| BM25 (keyword) | 19% | 1,110 |
| Vector RAG (Gemini embeddings) | 14% | 1,127 |

**With the same budget, the graph finds about 5× more of the affected code than vector RAG.**

### 3. A graph that improves itself

Static parsing can't see everything: dunder methods, dynamic dispatch, `with` blocks. So CodeGraph **learns from execution**: `learn.py` takes calls seen at runtime that the graph is missing and writes them into HydraDB as `CALLS {how: "runtime"}` edges.

To keep the evaluation honest, the trace is **split**. The graph learns from *train* runs (get, post, redirect, session with cookies) and is scored only on *test* runs it never saw (put, patch, delete, head, options, auth, 404).

| Held-out test runs | Recall |
|---|---|
| CodeGraph, before learning | 78% |
| **CodeGraph, after learning** | **98%** |
| BM25 | 25% |
| Vector RAG | 20% |

### 4. A real agent: Claude Code (Haiku) with and without CodeGraph

`agent_bench.py` runs Claude Code headless on the same questions, once with the CodeGraph MCP server and once with grep/read only. It checks each answer for the real callers: either by name, or by a cited line inside the caller next to its file name. 3 questions × 2 runs each:

| | CodeGraph | grep only |
|---|---|---|
| **Callers found** | **18/18** | 7/18 |
| API time | **57s** | 103s |
| Cost | $0.10 | $0.23 |

Cost varies from run to run because of prompt caching (in one earlier single run, CodeGraph was 7% *more* expensive). Across all runs it came out **about 30% cheaper**. The consistent wins are **completeness** and **speed**. On `CaseInsensitiveDict.__setitem__`, grep found **0/3** callers in every run, because nothing calls it by name. The runtime-learned graph found 3/3 every time.

### What didn't win (honestly)

On a strong model (Opus), grep-only answers on `requests` were **as good as CodeGraph's** at the same cost. `requests` is small and cleanly named, so grepping it is cheap. CodeGraph's edge shows up with **smaller models**, **hidden or dynamic calls**, and, we expect, **larger codebases** (not measured yet).

---

## How it works

```
 Python repo ──► extract.py ──► graph.json ──► load.py ──► HydraDB
   (ast)        files, classes,               UNWIND/MERGE    │
                functions + CALLS,                            │  algo.SSpaths
                CONTAINS, IMPORTS,                            │  (in-database
                INHERITS edges                                │   traversal)
                                                              ▼
 real runs ──► trace_calls.py ──► learn.py ──► + runtime edges
 (sys.setprofile)                                             │
                                                              ▼
                              context.py: find / callers / callees / context
                                                              │
                                                              ▼
                              mcp_server.py ──► Claude Code / Cursor
```

**1. Parse (`extract.py`).** Python's `ast` turns the repo into nodes (`File`, `Class`, `Function` with their source code and docstrings) and edges. Each call is resolved to the function it actually calls, and every edge records *how* it was resolved:

| `how` | Example |
|---|---|
| `self` | `self.send()` → a method of the same class |
| `local` / `import` / `module` | followed through the file's own imports |
| `init` | `Session()` → `Session.__init__` |
| `override` | `self.send()` in a mixin → the subclass's `Session.send` |
| `super` | `super().__init__()` → the parent's method |
| `property` | reading `r.content` → `Response.content` |
| `guess` | `session.request()` where only one method in the repo has that name |
| `runtime` | learned from a real execution trace |

**2. Load (`load.py`).** Nodes are bulk-loaded with `UNWIND $rows AS row MERGE (n {id: row.id}) SET n:Label, ...`, then edges are added.

**3. Traverse (`context.py`).** Callers and callees are found with **`algo.SSpaths`**, HydraDB's single-source path procedure, using `relDirection: 'incoming'` or `'outgoing'`. The walk runs **inside the database**, and the returned nodes already carry their code, so building context takes one query.

**4. Learn (`trace_calls.py`, `learn.py`).** A local HTTP server plus real `requests` calls, recorded with `sys.setprofile`, give independent ground truth. The calls the static parser missed are written back into the graph.

**5. Serve (`mcp_server.py`).** Four MCP tools:

| Tool | Answers |
|---|---|
| `find_symbol(name)` | Where is this? (and which `send` do you mean?) |
| `who_calls(symbol, depth)` | What breaks if I change it? |
| `what_it_calls(symbol, depth)` | What does it depend on? |
| `get_context(symbol, depth)` | The code of the target, its callers and its callees, in one block |

## HydraDB features used

- **Bolt protocol with the standard `neo4j` Python driver**
- **Labels and properties**, with batched `UNWIND ... MERGE ... SET` writes
- **`algo.SSpaths`** for in-database multi-hop traversal in both directions
- **Relationship properties** (`how`) for edge provenance

Notes from building on HydraDB:
- Node `id`s must be non-negative integers, so the text key is stored as a `key` property.
- Variable-length `MATCH` needs a fixed source id and only walks forward. Backward walks use `algo.SSpaths` with `relDirection: 'incoming'`.
- `pathCount` in `algo.SSpaths` caps the **total** number of paths returned, not the number per target.
- **Bug found:** with `CLOUD_PROVIDER=local`, writes fail after restarting `graph-node` on an existing store (`PutMode::Update not yet implemented by LocalFileSystem`). Details are in [`bug.md`](bug.md).

---

## Setup

### 1. Run HydraDB

```bash
sudo apt-get install -y build-essential clang libclang-dev cmake pkg-config \
  libcypher-parser-dev libgraphblas-dev curl git
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh && . "$HOME/.cargo/env"

git clone https://github.com/hydra-db/hydradb.git && cd hydradb
bash scripts/install_lagraph.sh "$HOME/.local/lagraph"
export LAGRAPH_LIB_DIR="$HOME/.local/lagraph/lib"

mkdir -p .hydradb/store .hydradb/cache
printf '%s\n' 'local-development-token-32-bytes' > .hydradb/auth-token
export CLOUD_PROVIDER=local LOCAL_PATH="$PWD/.hydradb/store" \
  GRAPH_NAMESPACE=default GRAPH_ID=default GRAPH_CELL_ID=cell-0 GRAPH_CELLS=cell-0 \
  GRAPH_NODE_ID=node-0 GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 \
  GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687 GRAPH_DATA_CACHE_DIR="$PWD/.hydradb/cache" \
  GRAPH_DATA_CACHE_PART_BYTES=4194304 GRAPH_DATA_CACHE_MAX_OPEN_FILES=512 \
  GRAPH_AUTH_TOKEN_FILE="$PWD/.hydradb/auth-token" GRAPH_ALLOW_PLAINTEXT=true \
  RUST_MIN_STACK=33554432
cargo run --locked --features server-runtime --bin graph-node
```

> Because of the restart bug above, wipe `.hydradb/store` and `.hydradb/cache` before every restart, then reload.

### 2. Build the graph

```bash
git clone https://github.com/psf/requests.git sample_repo   # next to this repo
cd codegraph
python3 -m venv myenv && source myenv/bin/activate
pip install neo4j mcp rank-bm25 google-genai python-dotenv urllib3 idna charset_normalizer certifi

python extract.py       # parse sample_repo into graph.json
python load.py          # load it into HydraDB
python trace_calls.py   # record real calls (train and test splits)
python learn.py         # add the runtime edges the parser missed
```

### 3. Reproduce the results

```bash
python bench.py                    # retrieval: graph vs BM25 vs vector (vector needs GEMINI_API_KEY in .env)
python bench.py trace_test.json    # held-out runs: recall at equal budget + tokens needed (run before and after learn.py)
python agent_bench.py --runs 2     # Claude Code (Haiku), with vs without CodeGraph
```

### 4. Use it from Claude Code

```bash
cd ../sample_repo
claude mcp add codegraph -- /path/to/codegraph/myenv/bin/python /path/to/codegraph/mcp_server.py
claude
> What breaks if I change Session.send? Use the codegraph tools.
```

## Files

| File | Purpose |
|---|---|
| `extract.py` | Parse a Python repo into `graph.json` (nodes, edges, provenance) |
| `load.py` | Load `graph.json` into HydraDB |
| `context.py` | `find`, `callers`, `callees`, `context`, built on `algo.SSpaths` |
| `trace_calls.py` | Ground truth: record real calls, split into train and test |
| `learn.py` | Self-improvement: write missing runtime calls into the graph |
| `bench.py` | Retrieval benchmark: graph vs BM25 vs vector at equal token budget |
| `agent_bench.py` | End-to-end benchmark with Claude Code, with and without CodeGraph |
| `mcp_server.py` | MCP server exposing the four tools |
| `mcp_test.py` | Talks to the MCP server over stdio, the way an agent does |
| `results/` | Saved answers and tables from `agent_bench.py` |

## Limitations

- Python only for now (the parser uses `ast`).
- Static resolution is heuristic: `guess` edges can be wrong, and calls through variables of unknown type are missed unless runtime learning adds them.
- Runtime learning only knows code paths that were actually executed.
- The benchmarks run on one small repo.

## Roadmap

- Benchmark on a large repository, with ground truth from its own test suite.
- `tests_for(symbol)`: "which tests do I need to run if I change this?", from test → function runtime edges.
- Incremental updates on every commit, re-parsing only the changed files.
- Other languages via tree-sitter.