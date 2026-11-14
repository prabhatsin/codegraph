"""Run Claude Code headless on the same questions, with and without codegraph,
and record cost, speed and whether the answer found the real callers."""
import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = Path("../sample_repo").resolve()   # the agent works inside this repo
OUT = Path("results")

# question -> callers a correct answer must cover. Each caller counts as found if the
# answer names it (any spelling listed) OR cites a line inside that function's body.
QUESTIONS = {
    "Session.send": [
        ("requests/sessions.py::Session.request", ["Session.request", "request()"]),
        ("requests/sessions.py::SessionRedirectMixin.resolve_redirects", ["resolve_redirects"]),
        ("requests/api.py::request", ["requests.get", "api.request", "requests.request", "api.py"]),
    ],
    "merge_cookies": [
        ("requests/sessions.py::Session.prepare_request", ["prepare_request"]),
        ("requests/sessions.py::SessionRedirectMixin.resolve_redirects", ["resolve_redirects"]),
        ("requests/sessions.py::Session.request", ["Session.request", "request()"]),
    ],
    "CaseInsensitiveDict.__setitem__": [
        ("requests/models.py::PreparedRequest.prepare_headers", ["prepare_headers"]),
        ("requests/models.py::PreparedRequest.prepare_body", ["prepare_body"]),
        ("requests/models.py::PreparedRequest.prepare_content_length", ["prepare_content_length"]),
    ],
}

# line span of every function, so "line 268 in sessions.py" can count as resolve_redirects
SPANS = {}
for n in json.load(open("graph.json"))["nodes"]:
    if n["kind"] == "Function":
        SPANS[n["id"]] = (n["file"].split("/")[-1], n["line"],
                          n["line"] + len(n["code"].splitlines()) - 1)

MODES = {
    # codegraph: the project's MCP config is loaded, codegraph tools pre-approved
    "codegraph": ["--allowedTools", "mcp__codegraph", "Read", "Grep", "Glob"],
    # grep only: --strict-mcp-config with no config file = no MCP servers at all
    "grep": ["--strict-mcp-config", "--allowedTools", "Read", "Grep", "Glob"],
}


def ask(question, mode, model):
    prompt = f"What breaks if I change {question}?"
    if mode == "codegraph":
        prompt += " Use the codegraph tools."
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json", *MODES[mode]]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"is_error": True, "result": proc.stdout + proc.stderr}


def cited_lines(answer):
    """(file, line) pairs the answer cites, e.g. 'Line 268 (sessions.py)' or
    'sessions.py:292'. A line only counts if a file name is written next to it,
    because the same number means different code in different files."""
    files = [(m.start(), m.group(1)) for m in re.finditer(r"(\w+\.py)", answer)]
    cites = set()
    for m in re.finditer(r"(?:lines?\s+|\.py:)(\d+)(?:\s*[-–]\s*(\d+))?", answer, re.I):
        near = [(abs(pos - m.start()), f) for pos, f in files if abs(pos - m.start()) <= 60]
        if near:
            f = min(near)[1]
            a, b = int(m.group(1)), int(m.group(2) or m.group(1))
            cites.update((f, n) for n in range(a, b + 1))
    return cites


def grade(answer, checks):
    cites = cited_lines(answer)
    found = []
    for key, names in checks:
        file, start, end = SPANS[key]
        by_name = any(name in answer for name in names)
        by_line = any(f == file and start <= n <= end for f, n in cites)
        found.append(by_name or by_line)
    return found


def regrade():
    """Re-score saved answers in results/ without asking Claude again."""
    rows = json.loads((OUT / "agent_bench.json").read_text())
    for r in rows:
        name = f"{r['question']}_{r['mode']}_{r['run']}".replace("/", "_")
        answer = (OUT / f"{name}.md").read_text()
        checks = QUESTIONS[r["question"]]
        hits = grade(answer, checks)
        r["found"] = f"{sum(hits)}/{len(hits)}"
        r["missed"] = [checks[i][0].split("::")[1] for i, h in enumerate(hits) if not h]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--runs", type=int, default=1, help="repeat each pair to average out noise")
    ap.add_argument("--regrade", action="store_true", help="re-score saved answers, no new runs")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    rows = regrade() if args.regrade else []
    for question, checks in ([] if args.regrade else QUESTIONS.items()):
        for mode in MODES:
            for run in range(1, args.runs + 1):
                print(f"asking [{mode:9}] {question}  (run {run}) ...", flush=True)
                r = ask(question, mode, args.model)
                answer = r.get("result", "")
                hits = grade(answer, checks)
                name = f"{question}_{mode}_{run}".replace("/", "_")
                (OUT / f"{name}.md").write_text(f"# {question} ({mode}, run {run})\n\n{answer}\n")
                rows.append({
                    "question": question, "mode": mode, "run": run,
                    "ok": not r.get("is_error", False),
                    "cost": r.get("total_cost_usd", 0.0),
                    "api_s": r.get("duration_api_ms", 0) / 1000,
                    "turns": r.get("num_turns", 0),
                    "output_tokens": r.get("usage", {}).get("output_tokens", 0),
                    "found": f"{sum(hits)}/{len(hits)}",
                    "missed": [checks[i][0].split("::")[1] for i, h in enumerate(hits) if not h],
                })

    (OUT / "agent_bench.json").write_text(json.dumps(rows, indent=2))

    lines = [f"# Claude Code ({args.model}): codegraph vs grep\n",
             "| Question | Mode | Run | Cost | API time | Turns | Output tokens | Found | Missed |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        status = "" if r["ok"] else " ⚠️ error"
        lines.append(f"| `{r['question']}` | {r['mode']}{status} | {r['run']} | ${r['cost']:.4f} | "
                     f"{r['api_s']:.0f}s | {r['turns']} | {r['output_tokens']} | {r['found']} | "
                     f"{', '.join(r['missed']) or '-'} |")
    lines.append("\n| Mode | Total cost | Total API time | Callers found |\n|---|---|---|---|")
    for mode in MODES:
        mine = [r for r in rows if r["mode"] == mode]
        found = sum(int(r["found"].split("/")[0]) for r in mine)
        total = sum(int(r["found"].split("/")[1]) for r in mine)
        lines.append(f"| {mode} | ${sum(r['cost'] for r in mine):.4f} | "
                     f"{sum(r['api_s'] for r in mine):.0f}s | {found}/{total} |")
    report = "\n".join(lines)
    (OUT / "agent_bench.md").write_text(report + "\n")
    print("\n" + report)
    print(f"\nFull answers saved in {OUT}/")


if __name__ == "__main__":
    main()