# Session.send (codegraph, run 1)

Here's what breaks if you change `Session.send`:

**Direct callers (1 hop):**
- `Session.request` (line 557) — the core method that all HTTP verb methods use
- `SessionRedirectMixin.resolve_redirects` (line 186) — redirect handling logic

**Indirect callers (2 hops):**
- All the convenience HTTP methods: `Session.get`, `Session.post`, `Session.put`, `Session.patch`, `Session.delete`, `Session.head`, `Session.options` (lines 655–742)
- The module-level `request` function in `requests/api.py` (line 24) — used for simple one-off requests

**Impact**: Changing the signature or behavior of `Session.send` will break the entire request pipeline. Since all HTTP verb methods flow through `Session.request` → `Session.send`, any change affects every HTTP call in the library. The redirect resolver also depends on it for following redirects.

The key constraint is that `Session.send` is the bridge between preparing a request and actually sending it to the adapter, so its interface is critical for internal consistency.
