# merge_cookies (codegraph, run 1)

Here's what breaks if you change `merge_cookies`:

**Direct callers (1 hop):**
1. **`Session.prepare_request`** (line 511) — Called when preparing requests. It merges session cookies with request-specific cookies in one of the core steps before transmission.
2. **`SessionRedirectMixin.resolve_redirects`** (line 186) — Called when following HTTP redirects to maintain cookie state across redirect chains.

**Indirect callers (2 hops):**
3. **`Session.request`** (line 557) — The main request method that kicks off the entire flow.
4. **`Session.send`** (line 752) — Sends already-prepared requests.

**Why it matters:** `merge_cookies` is the central cookie-merging function. It takes a `CookieJar` and additional cookies (either a dict or another `CookieJar`) and returns a merged result. Changing its signature, return type, or behavior would break cookie handling across:
- Session-wide cookies being applied to individual requests
- Request-specific cookies being added
- Cookie state persistence through redirects

Any change to its parameters, return type, or the way it handles different input types (dict vs CookieJar) would cascade through all request handling.
