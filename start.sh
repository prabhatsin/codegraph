#!/usr/bin/env bash
# Start HydraDB's graph-node for local development on a FRESH store.
# Usage:  bash start.sh [path/to/hydradb]   (default: ../hydradb next to codegraph)
# The store is wiped on every start: with CLOUD_PROVIDER=local, writes fail after a
# restart on an existing store (see bug.md). Re-run `codegraph.py index` afterwards.
set -euo pipefail
HYDRA="${1:-$(cd "$(dirname "$0")/../hydradb" && pwd)}"
cd "$HYDRA"

rm -rf .hydradb/store .hydradb/cache
mkdir -p .hydradb/store .hydradb/cache
printf '%s\n' 'local-development-token-32-bytes' > .hydradb/auth-token

[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
export LAGRAPH_LIB_DIR="${LAGRAPH_LIB_DIR:-$HOME/.local/lagraph/lib}"
export CLOUD_PROVIDER=local LOCAL_PATH="$PWD/.hydradb/store" \
  GRAPH_NAMESPACE=default GRAPH_ID=default GRAPH_CELL_ID=cell-0 GRAPH_CELLS=cell-0 \
  GRAPH_NODE_ID=node-0 GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 \
  GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687 GRAPH_DATA_CACHE_DIR="$PWD/.hydradb/cache" \
  GRAPH_DATA_CACHE_PART_BYTES=4194304 GRAPH_DATA_CACHE_MAX_OPEN_FILES=512 \
  GRAPH_AUTH_TOKEN_FILE="$PWD/.hydradb/auth-token" GRAPH_ALLOW_PLAINTEXT=true \
  RUST_MIN_STACK=33554432
exec cargo run --locked --features server-runtime --bin graph-node
