# Writes fail after restarting `graph-node` on an existing local store

## Summary

With `CLOUD_PROVIDER=local`, a `graph-node` that starts on a **fresh** store accepts reads and writes normally. If the node is stopped and started again on the **same** store directory, reads still work, but **every write fails** with `internal query execution error`.

## Environment

- HydraDB `main`, build commit `916637477f3f` (graph-node `0.1.0+916637477f3f`)
- Ubuntu 24.04, x86_64
- Built with `cargo run --locked --features server-runtime --bin graph-node`
- Python `neo4j` driver 6.x over Bolt (`bolt://127.0.0.1:7687`)
- Local-development environment from the README:
  `CLOUD_PROVIDER=local`, `LOCAL_PATH=$PWD/.hydradb/store`, `GRAPH_ALLOW_PLAINTEXT=true`, single node `node-0`, single cell `cell-0`

## Steps to reproduce

1. Start with an empty store and run the node:
   ```
   rm -rf .hydradb/store .hydradb/cache && mkdir -p .hydradb/store .hydradb/cache
   cargo run --locked --features server-runtime --bin graph-node
   ```
2. Write something. This works:
   ```cypher
   MERGE (a {id: 1})-[:CALLS {how: 'x'}]->(b {id: 2})
   ```
3. Stop the node with `Ctrl+C`, then start it again **without** clearing `.hydradb/store`.
4. Run a read. This works:
   ```cypher
   MATCH (a {id: 1})-[:CALLS]->(b) RETURN b.id AS id
   ```
5. Run any write, e.g. the same `MERGE` as in step 2, or a batched
   `UNWIND $rows AS row MERGE (n {id: row.id}) SET n:Function, n.name = row.name`.

## Expected

After a restart, the node takes over the existing store and accepts writes, as it does on a fresh store.

## Actual

Every write is rejected. The client receives:

```
neo4j.exceptions.DatabaseError: {neo4j_code: Neo.DatabaseError.General.UnknownError}
{message: internal query execution error} {gql_status: 50N42}
```

The server log shows the underlying cause:

```json
{"level":"WARN","message":"Bolt suppressed internal graph error",
 "error_message":"object store error: Operation `put_opts` with mode `PutMode::Update` not yet implemented by LocalFileSystem(file:///.../.hydradb/store).",
 "error_type":"hydradb","target":"hydradb"}
```

## Likely cause

When it restarts, the node has to update its existing writer lease or manifest object with a conditional put (`PutMode::Update`). The `object_store` crate's `LocalFileSystem` backend doesn't implement `PutMode::Update`. On a fresh store only create-only puts are needed, which `LocalFileSystem` does support. The startup log reports `object store passed the create-only probe: writers allowed`, so the problem only appears on the first update.

## Impact

- Local development can't survive a node restart: the only recovery is to delete the store and reload all data.
- The client only sees a generic `internal query execution error`, so the cause is hard to find without reading the server log.

## Workaround

Wipe the local store before every restart and reload the data:

```
rm -rf .hydradb/store .hydradb/cache && mkdir -p .hydradb/store .hydradb/cache
```

Using MinIO (`just minio-smoke` setup) instead of `CLOUD_PROVIDER=local` probably avoids it, because S3-compatible stores support conditional updates. I haven't verified that.

## Suggestions

1. Support restart on `CLOUD_PROVIDER=local`, for example with a file-lock or rename-based compare-and-swap for lease/manifest updates in local mode.
2. Failing that, detect this at startup and refuse to start (or warn loudly) instead of passing the create-only probe and failing on the first write.
3. Show the object-store error, or at least a clearer message, to the client instead of `internal query execution error`.
4. Document in the README that local-mode stores can't be reopened for writes.