"""Ground truth from a repo's own test suite: run pytest under a profiler and record
every package -> package call, plus which functions each test exercised.

    CODEGRAPH_REPO=rich python trace_pytest.py
"""
import json
import sys
from pathlib import Path

import pytest

from config import NAME, PKG_DIRS, REPO_ROOT, SRC, data_file

ROOT = REPO_ROOT.resolve()
PKGS = [d.resolve() for d in PKG_DIRS]
SRC_ABS = SRC.resolve()

edges = {"train": set(), "test": set()}
test_hits = {}        # test id -> functions it ran (any depth)
current = {"test": None, "split": None}


def key_of(frame):
    path = Path(frame.f_code.co_filename)
    if not any(p in path.parents for p in PKGS):
        return None
    qual = frame.f_code.co_qualname.split(".<locals>")[0]
    return f"{path.relative_to(SRC_ABS)}::{qual}"


def profiler(frame, event, arg):
    if event != "call" or current["test"] is None:
        return
    callee = key_of(frame)
    if not callee:
        return
    test_hits[current["test"]].add(callee)
    caller = frame.f_back and key_of(frame.f_back)
    if caller and caller != callee:
        edges[current["split"]].add((caller, callee))


def split_for(test_file):
    """Every other test file goes to train / test, so the split is stable."""
    files = sorted(p.name for p in ROOT.rglob("test_*.py"))
    return "train" if files.index(test_file) % 2 == 0 else "test"


class Recorder:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        current["test"] = item.nodeid
        current["split"] = split_for(Path(item.fspath).name)
        test_hits.setdefault(item.nodeid, set())
        sys.setprofile(profiler)
        try:
            yield
        finally:
            sys.setprofile(None)
            current["test"] = None


if __name__ == "__main__":
    sys.path.insert(0, str(SRC_ABS))   # import the repo's copy of the package
    code = pytest.main([str(ROOT), "-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT)],
                       plugins=[Recorder()])
    train, test = edges["train"], edges["test"]
    data_file("trace_train.json").write_text(json.dumps(sorted(train), indent=1))
    data_file("trace_test.json").write_text(json.dumps(sorted(test), indent=1))
    data_file("trace_edges.json").write_text(json.dumps(sorted(train | test), indent=1))
    data_file("test_calls.json").write_text(json.dumps(
        {t: sorted(f) for t, f in test_hits.items()}, indent=1))
    print(f"\n[{NAME}] pytest exit code {code}")
    print(f"train edges: {len(train)}   test edges: {len(test)}   all: {len(train | test)}")
    print(f"test edges never seen in train: {len(test - train)}")
    print(f"tests recorded: {len(test_hits)}   functions exercised: "
          f"{len(set().union(*test_hits.values()))}")
