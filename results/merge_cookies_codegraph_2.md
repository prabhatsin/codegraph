# merge_cookies (codegraph, run 2)

Here's what breaks if you change `merge_cookies` (at `requests/cookies.py:604`):

**Direct callers (1 hop):**
- `requests/sessions.py::Session.prepare_request` (line 511)
- `requests/sessions.py::SessionRedirectMixin.resolve_redirects` (line 186)

**Indirect callers (2 hops):**
- `requests/sessions.py::Session.request` (line 557)
- `requests/sessions.py::Session.send` (line 752)

The two direct callers handle the core cookie-merging logic: `prepare_request` merges cookies when preparing each request, and `resolve_redirects` merges cookies during redirect handling. Any change to `merge_cookies` would cascade up to affect the overall `Session.request` and `Session.send` flows, impacting all HTTP requests made through sessions.
