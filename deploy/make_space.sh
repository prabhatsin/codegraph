#!/usr/bin/env bash
# Build the Hugging Face Space folder from this project.
# Run from Hydradb_Hackethon_Nov14/:   bash codegraph/deploy/make_space.sh codegraph-space
set -euo pipefail
SPACE="${1:-codegraph-space}"
DEPLOY="$(cd "$(dirname "$0")" && pwd)"
[ -d "$SPACE/.git" ] || { echo "Clone your Space first: git clone https://huggingface.co/spaces/<user>/codegraph $SPACE"; exit 1; }

mkdir -p "$SPACE/codegraph/data/rich" "$SPACE/codegraph/results/rich" "$SPACE/rich_repo" "$SPACE/Frontend"
cp codegraph/config.py codegraph/context.py codegraph/load.py codegraph/learn.py codegraph/ui_server.py "$SPACE/codegraph/"
cp codegraph/data/rich/graph.json codegraph/data/rich/trace_train.json \
   codegraph/data/rich/summary.json codegraph/data/rich/bench_results.json "$SPACE/codegraph/data/rich/"
cp codegraph/results/rich/agent_bench.json "$SPACE/codegraph/results/rich/"
rm -rf "$SPACE/rich_repo/rich" && cp -r rich_repo/rich "$SPACE/rich_repo/"
rm -rf "$SPACE/Frontend/static" && cp -r Frontend/index.html Frontend/static "$SPACE/Frontend/"
cp "$DEPLOY/Dockerfile" "$DEPLOY/start.sh" "$SPACE/"
cp "$DEPLOY/space_README.md" "$SPACE/README.md"
find "$SPACE" -name "__pycache__" -prune -exec rm -rf {} +
echo "Space folder ready: $SPACE  ($(du -sh "$SPACE" --exclude=.git | cut -f1))"
