#!/usr/bin/env bash
# Boot: start HydraDB on a fresh local store, load the rich graph + runtime-learned
# edges, then serve the CodeGraph UI and API on $PORT.
set -euo pipefail
GRAPH_NODE="${GRAPH_NODE:-/usr/local/bin/graph-node}"
PY="${PY:-python3}"
STORE=/tmp/hydradb
rm -rf "$STORE" && mkdir -p "$STORE/store" "$STORE/cache"
printf '%s\n' 'local-development-token-32-bytes' > "$STORE/auth-token"

export CLOUD_PROVIDER=local LOCAL_PATH="$STORE/store" \
  GRAPH_NAMESPACE=default GRAPH_ID=default GRAPH_CELL_ID=cell-0 GRAPH_CELLS=cell-0 \
  GRAPH_NODE_ID=node-0 GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 \
  GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687 GRAPH_DATA_CACHE_DIR="$STORE/cache" \
  GRAPH_DATA_CACHE_PART_BYTES=4194304 GRAPH_DATA_CACHE_MAX_OPEN_FILES=512 \
  GRAPH_AUTH_TOKEN_FILE="$STORE/auth-token" GRAPH_ALLOW_PLAINTEXT=true \
  GRAPH_USAGE_REPORT_ENABLED=false RUST_MIN_STACK=33554432 \
  GRAPH_BOLT_ADDR=127.0.0.1:7687 GRAPH_HTTP_ADDR=127.0.0.1:8443 GRAPH_ADMIN_ADDR=127.0.0.1:9090

echo "[codegraph] starting HydraDB"
"$GRAPH_NODE" > /tmp/graph-node.log 2>&1 &
for i in $(seq 1 120); do
  "$PY" -c "import socket; socket.create_connection(('127.0.0.1', 7687), 1)" 2>/dev/null && break
  sleep 1
done
sleep 2

cd "$(dirname "$0")/codegraph"
echo "[codegraph] loading the rich graph into HydraDB"
"$PY" load.py
echo "[codegraph] adding the calls learned from rich's test suite"
"$PY" learn.py | tail -1
echo "[codegraph] serving on 0.0.0.0:${PORT:-7860}"
CODEGRAPH_UI_PORT="${PORT:-7860}" exec "$PY" ui_server.py
