

'''
What's going on: 
HydraDB saves your graph in the .hydradb/store folder. When the server starts, it “claims” that
folder so that only one server writes to it at a time. On a fresh, empty folder that claim 
works. On a folder an earlier server already used, the server has to update the old claim. 
In local mode, HydraDB doesn't support that update yet, so after a restart:



# reads still work (context.py, bench.py)
# writes fail with “internal query execution error” (load.py, learn.py)


When to wipe: only if you stop the server and start it again (Ctrl+C, a laptop reboot, a closed terminal). In that case, start the server like this:


#!----------------------------------------
rm -rf .hydradb/store .hydradb/cache
mkdir -p .hydradb/store .hydradb/cache
cargo run --locked --features server-runtime --bin graph-node
#!--------------------------------------------------------


Then in the codegraph terminal:

python load.py
python learn.py

Wiping is safe because the real data lives in graph.json and the trace files, so you can
rebuild the database from them in seconds.


About the bug report: it's optional, but it helps you in a hackathon run by the HydraDB team. 
Posting in their Discord shows you used the database seriously. Something like: 
“With CLOUD_PROVIDER=local, restarting graph-node on an existing store makes all writes 
fail with PutMode::Update not yet implemented by LocalFileSystem. Fresh stores work.”

'''