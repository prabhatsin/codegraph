# Session.send (grep, run 2)

Based on my search, here's what would break if you change `Session.send`:

**Direct callers within the Session class:**
1. **`resolve_redirects()` method** (line 292) — calls `Session.send()` to handle each redirect
2. **`request()` method** (line 651) — the core HTTP method that all verb methods (`.get()`, `.post()`, etc.) ultimately call

**The method hierarchy:**
- The signature is defined abstractly in `SessionRedirectMixin` (line 132)
- Implemented concretely in the `Session` class (line 752)

**Impact of changing the signature:**
- Any signature changes (parameter names, types, return type) would break:
  - The two internal calls above
  - All test code that directly calls `.send()` (40+ test locations)
  - Any user code that calls `.send()` directly
  - Any subclasses that override `.send()`

**The signature details (current):**
```python
def send(self, request: PreparedRequest, **kwargs: Any) -> Response:
```

The `**kwargs` captures options like `stream`, `verify`, `cert`, `proxies`, `timeout`, `allow_redirects` — used for both setting defaults and passing to adapters and hooks.

What specific change are you considering? The impact will depend on whether you're changing parameters, return type, or behavior.
