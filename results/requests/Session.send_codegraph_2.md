# Session.send (codegraph, run 2)

Here's what calls `Session.send` and would break if you change it:

**Direct callers (1 hop):**
- `Session.request()` (line 557) — the core method that initiates HTTP requests
- `SessionRedirectMixin.resolve_redirects()` (line 186) — handles HTTP redirects by resending

**Indirect callers (2 hops):**
- `requests.api.request()` (line 24) — the top-level module API
- All HTTP verb shortcuts: `Session.get()`, `Session.post()`, `Session.put()`, `Session.patch()`, `Session.delete()`, `Session.head()`, `Session.options()`

**Bottom line:** Changing `Session.send`'s signature or behavior would break the entire HTTP request chain — from high-level API calls down through all the convenience methods. Any change to parameters, return type, or exceptions would ripple through the entire library's public interface.
