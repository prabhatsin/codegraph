# Session.send (grep, run 1)

Based on my analysis, changing `Session.send()` would break several critical areas:

## Direct Callers

1. **Internal redirect handling** (`src/requests/sessions.py:292`) — `resolve_redirects()` calls `self.send()` recursively to follow redirects. Changes to the method signature or behavior would break redirect handling.

2. **The main `request()` method** (`src/requests/sessions.py:651`) — All high-level methods (`get()`, `post()`, `put()`, `patch()`, `delete()`, `head()`, `options()`) flow through `request()`, which calls `send()`. Any signature change breaks all of them.

## What Would Break Specifically

**Signature changes:** Any modification to the method signature (parameters or return type) would break:
- Test code that calls `session.send()` directly (at least 10+ test cases in `test_requests.py`)
- User code that prepares requests manually and calls `send()` directly (documented in `docs/user/advanced.rst`)
- Subclasses that might override this method

**Behavioral changes** to the current implementation would break:
- **Cookie handling** — lines 799-803 extract and persist cookies. Removing this breaks cookie sessions.
- **Hook dispatch** — line 791 dispatches response hooks. Removing this breaks response hook callbacks.
- **Elapsed time tracking** — lines 781-788. Removing this breaks response timing information.
- **Redirect handling** — lines 802-824. The recursive call and history building depends on specific behavior.
- **Content streaming** — line 827. Not pre-reading content when `stream=False` breaks content access patterns.
- **Adapter selection** — line 778. The dynamic adapter lookup for different schemes must work correctly.

**The safest change:** Adding new optional parameters (with defaults) would be forward-compatible, but removing parameters, changing return types, or altering the flow of cookie handling, hooks, or redirects would cause failures throughout the codebase.
