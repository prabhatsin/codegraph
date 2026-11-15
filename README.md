# CodeGraph

**A context layer for coding agents. It walks a codebase's call graph in HydraDB, so agents get exactly the code they need instead of burning tokens on whole files.**

Built for the HydraDB 48-hour hackathon, Track 2: *the context layer for agents, traversing structure instead of burning tokens.*

**Live demo:** https://YOUR-USERNAME-codegraph.hf.space (HydraDB + the CodeGraph UI, loaded with `rich`; every click is a real HydraDB query)

```bash
python codegraph.py index ~/code/any-python-repo    # parse it into a graph in HydraDB
python codegraph.py learn ~/code/any-python-repo    # optional: learn hidden calls from its test suite
python codegraph.py serve ~/code/any-python-repo    # MCP server for Claude Code, Cursor, ...
```

---

## The problem

Ask a coding agent "what breaks if I change `Console.print`?" and it has two options:

- **grep and read files.** That costs tokens and turns, and it can't see calls that never write the function's name. In Python, `console.print(table)` runs `Table.__rich_console__`, `a + b` runs `Text.__add__`, and `with console:` runs `Console.__enter__`.
- **Vector RAG.** That finds code that *looks like* the question. "Who calls X" is a question about structure, though, and similar-looking text tells you nothing about what calls what.

CodeGraph answers these questions by **walking edges in a graph database**: one query, the exact set of functions, only their code.

## Results

### Headline: `rich`, 100 files, ground truth from its own 956 tests

The ground truth is **what Python actually executed**: we run `rich`'s own pytest suite under a profiler and record every function → function call, 1,475 of them. Test files are split in half. The graph may learn from the first half, and it is **scored only on the second half**, which it never saw. The questions are "what breaks if I change X?" and "what does X depend on?", within 2 hops (715 questions).

| Method | Recall | Precision* | F1 | Tokens needed to find what CodeGraph found |
|---|---|---|---|---|
| **CodeGraph (HydraDB)** | **81%** | **90%** | **0.85** | **2,476 (1×)** |
| Vector RAG (Gemini embeddings) | 10% | 21% | 0.14 | 58,963 (**23.8×**) |
| BM25 (keyword) | 16% | 28% | 0.20 | 64,215 (25.9×) |
| Open every relevant file (grep + read) | — | — | — | 34,119 (13.8×) |

*Recall and precision for the retrievers are measured at the **same token budget** CodeGraph used.*
*\*Precision is judged only on functions the tests ran, because a returned function that never ran may be a real but untested caller. It is a lower bound.*

**To find the same callers, vector RAG reads about 24× more tokens and opening files reads about 14× more. CodeGraph's answers are 90% precise.**

### The gap grows with the size of the codebase

| Repo | Files | Ground truth | Tokens: whole files ÷ CodeGraph | Tokens: vector ÷ CodeGraph |
|---|---|---|---|---|
| `requests` | 19 | 153 calls (13 hand-written scenarios) | 10.5× | 9.3× |
| **`rich`** | 100 | 1,475 calls (956 real tests) | **13.8×** | **23.8×** |

`click` (17 large files, 2,625 tests) ran with **no configuration at all**: on held-out tests, CodeGraph needed **24× fewer tokens** than opening the files, with 92% recall. That was measured on our test machine; reproduce it with the three commands at the top.

### Why it's accurate: learning hidden calls from the test suite

A parser reading the code can't see calls Python makes behind the scenes: protocol methods (`__rich_console__`), operators (`__add__`), truthiness (`__bool__`), `with` blocks, and objects called like functions. So `learn` runs the repo's own tests and writes the calls it sees, but the graph lacks, into HydraDB as `CALLS {how: "runtime"}` edges. On `rich`, that's 447 new edges.

| Held-out tests (never learned from) | `requests` | `rich` |
|---|---|---|
| Recall, code only | 78% | 46% |
| **Recall after learning** | **98%** | **81%** |

**Tests are optional.** Without them, CodeGraph still works from the code alone: on `rich`, that's 46% recall at **19× fewer tokens** than opening files.

### A real agent: Claude Code (Haiku) with and without CodeGraph

`agent_bench.py` runs Claude Code headless on 3 questions per repo, once with the CodeGraph MCP server and once with grep/read only, 2 runs each (12 sessions per repo). Each answer is checked for the real callers: by name, by `method()`, or by a cited line inside the caller next to its file name.

| | CodeGraph | grep only |
|---|---|---|
| **Callers found** (`requests` + `rich`) | **36/36** | 17/36 |
| Cost | **$0.28** | $0.84 (3.0× more) |
| API time | **122s** | 385s (3.2× slower) |

The pattern is consistent: on a function **called by name** (`Text.truncate`), grep does fine (5/6). On **hidden calls** (`Style.__add__` runs on `style + style`, `Text.__len__` on `len(text)`, `CaseInsensitiveDict.__setitem__` on `headers[k] = v`), grep found **5/18** and CodeGraph **18/18**, because the graph learned those calls from the test suite. One grep run started a subagent and cost $0.33 on its own; without it grep is still more expensive ($0.51 for 11 runs). Costs vary run to run with prompt caching. Saved answers and tables are in `results/<repo>/`.

### What didn't win (honestly)

On a strong model (Opus), grep-only answers on the small `requests` repo were **as good as CodeGraph's** at the same cost. Grepping 19 well-named files is cheap. CodeGraph's edge shows up with **bigger repos**, **smaller models** and **hidden calls**.

---

## How it works

```
 any Python repo ──► extract.py ──► graph.json ──► load.py ──► HydraDB
   (ast)          files, classes,                 UNWIND/MERGE   │
                  functions + CALLS,                             │ algo.SSpaths
                  CONTAINS, IMPORTS,                             │ (in-database
                  INHERITS edges                                 │  traversal)
                                                                 ▼
 its test suite ──► trace_pytest.py ──► learn.py ──► + runtime edges
 (sys.setprofile)                                                │
                                                                 ▼
                         context.py: find / callers / callees / context
                                                                 │
                                                                 ▼
                         mcp_server.py ──► Claude Code / Cursor / any MCP agent
```

**1. Parse (`extract.py`).** Python's `ast` turns the repo into nodes (`File`, `Class`, `Function`, with their source code and docstrings) and edges. Each call is resolved to the function it actually calls, and each edge records *how* it was resolved:

| `how` | Example |
|---|---|
| `self` | `self.render()` → a method of the same class |
| `local` / `import` / `module` | followed through the file's own imports |
| `init` | `Panel(...)` → `Panel.__init__` |
| `override` | `self.send()` in a mixin → the subclass's `Session.send` |
| `super` | `super().__init__()` → the parent's method |
| `property` | reading `r.content` → `Response.content` |
| `guess` | `x.method()` where only one method in the repo has that name |
| `runtime` | learned from a real execution trace |

**2. Load (`load.py`).** Nodes are bulk-loaded with `UNWIND $rows AS row MERGE (n {id: row.id}) SET n:Label, ...`, then edges are added.

**3. Traverse (`context.py`).** Callers and callees come from **`algo.SSpaths`**, HydraDB's single-source path procedure, with `relDirection: 'incoming'` or `'outgoing'`. The walk runs **inside the database**, and the returned nodes already carry their code, so building context takes one query.

**4. Learn (`trace_pytest.py`, `learn.py`).** The repo's own pytest suite runs under `sys.setprofile`. Calls the parser missed are written back into the graph.

**5. Serve (`mcp_server.py`, `ui_server.py`).** Four MCP tools for agents, and a live web UI for people:

| Tool | Answers |
|---|---|
| `find_symbol(name)` | Where is this? (and which `send` do you mean?) |
| `who_calls(symbol, depth)` | What breaks if I change it? |
| `what_it_calls(symbol, depth)` | What does it depend on? |
| `get_context(symbol, depth)` | The code of the target, its callers and its callees, in one block |

**Live UI (`Frontend/`, served by `ui_server.py`).** Four views on top of the same HydraDB queries: **Overview** (benchmark, live graph stats), **Blast radius** (callers/callees in rings, learned edges in violet, the HydraDB query time), **Token map** (every file sized by tokens: what grep would open vs the slices CodeGraph sends) and **Agent race** (the real Claude Code runs). `Frontend/static/` is an offline version with the data exported by `export_ui.py`.

**Works on any Python repo.** `config.py` finds the source folder (`src/` if present), every package in it (folders with `__init__.py`, skipping tests, docs and examples), and keeps each repo's data in `data/<package>/`. No code changes are needed for a new repo.

## HydraDB features used

- **Bolt protocol with the standard `neo4j` Python driver**
- **Labels and properties**, with batched `UNWIND ... MERGE ... SET` writes
- **`algo.SSpaths`** for in-database multi-hop traversal in both directions
- **Relationship properties** (`how`) for edge provenance

Notes from building on HydraDB:
- Node `id`s must be non-negative integers, so the text key is stored as a `key` property.
- Variable-length `MATCH` needs a fixed source id and only walks forward. Backward walks use `algo.SSpaths` with `relDirection: 'incoming'`.
- `pathCount` in `algo.SSpaths` caps the **total** number of paths returned, not the number per target.
- Batched `UNWIND` edge writes can't carry relationship properties, so edges with `how` are written one at a time (about 50s for `rich`'s 2,832 edges).
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
bash /path/to/codegraph/start.sh     # starts graph-node on a fresh local store
```

`start.sh` sets the local-development environment and wipes the store first, because of the restart bug above. After a restart, run `index` (and `learn`) again.

### 2. Index a repo

```bash
cd codegraph
python3 -m venv myenv && source myenv/bin/activate
pip install neo4j mcp rank-bm25 google-genai python-dotenv pytest

python codegraph.py index ../rich_repo   # parse + load into HydraDB
python codegraph.py learn ../rich_repo   # run its tests, add the runtime calls
```

### 3. Use it from Claude Code

```bash
cd ../rich_repo
claude mcp add codegraph -- /path/to/codegraph/myenv/bin/python /path/to/codegraph/mcp_server.py
claude
> What breaks if I change Console.print? Use the codegraph tools.
```

### 4. Open the live UI

```bash
python ui_server.py ../rich_repo        # then open http://localhost:8765
```

### 5. Deploy (Hugging Face Spaces, Docker)

`deploy/` holds a Dockerfile built on the official `ghcr.io/hydra-db/hydradb:0.4.0` image. On boot, `deploy/start.sh` starts HydraDB on a fresh store, loads the graph and the learned calls, and serves the UI on port 7860.

```bash
git clone https://huggingface.co/spaces/<user>/codegraph codegraph-space
bash codegraph/deploy/make_space.sh codegraph-space      # run from the folder above codegraph/
cd codegraph-space && git add -A && git commit -m deploy && git push
```

### 6. Reproduce the results

```bash
python codegraph.py bench ../rich_repo     # recall, precision, F1, tokens (vector needs GEMINI_API_KEY in .env)
python agent_bench.py --runs 2             # Claude Code (Haiku) with vs without CodeGraph, on requests
```

For `requests`, whose own tests need internet, the ground truth is 13 hand-written scenarios (`trace_calls.py`) instead of its test suite.

## Files

| File | Purpose |
|---|---|
| `codegraph.py` | Command line: `index`, `learn`, `serve`, `bench` for any repo |
| `config.py` | Finds the source folder and packages of the repo you point it at |
| `extract.py` | Parse a Python repo into a graph (nodes, edges, provenance) |
| `load.py` | Load the graph into HydraDB |
| `context.py` | `find`, `callers`, `callees`, `context`, built on `algo.SSpaths` |
| `trace_pytest.py` | Run a repo's own tests under a profiler: ground truth and learning data |
| `learn.py` | Write runtime calls the parser missed into HydraDB |
| `mcp_server.py` | MCP server exposing the four tools |
| `ui_server.py` | Live web UI and JSON API (`/api/repo`, `/api/walk`, `/api/find`, `/api/agent_runs`) |
| `export_ui.py` | Export the graph walks for the offline page (`Frontend/static/data.js`) |
| `Frontend/` | The web UI: `index.html` (live), `static/` (offline), `design/` (original mockups) |
| `deploy/` | Dockerfile, boot script and `make_space.sh` for the hosted demo |
| `bench.py` | Recall, precision, F1 and tokens: CodeGraph vs vector vs BM25 vs whole files |
| `agent_bench.py` | End-to-end benchmark with Claude Code, with and without CodeGraph |
| `trace_calls.py` | Hand-written `requests` scenarios (the evaluation fixture for `requests`) |
| `data/<repo>/` | Graph, traces and cached embeddings for each indexed repo |
| `results/` | Saved answers and tables from `agent_bench.py` |

## Limitations

- Python only for now (the parser uses `ast`).
- Static resolution is heuristic: `guess` edges can be wrong, and calls through objects of unknown type are missed unless learning adds them.
- Learning only knows code paths the tests actually run. The train/test split is by test file, and files share code paths, so after-learning recall is somewhat optimistic. The 381 `rich` test calls never seen in training are the strictly unseen part.
- Token counts are estimated as characters ÷ 4, the same way for every method.
- One HydraDB database holds one repo at a time; switching repos means a fresh store and a re-index.

## Roadmap

- Confidence on edges: confirmed by tests > static > guess, so the most trusted code is sent first.
- `get_context(symbol, max_tokens)`, which fits the agent's token budget.
- A CLI for agents without MCP (Pi, Aider).
- 95% confidence intervals on the benchmark numbers.
- Incremental updates on every commit, re-parsing only the changed files.
- Other languages via tree-sitter.
