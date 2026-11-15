# CaseInsensitiveDict.__setitem__ (grep, run 1)

Based on my analysis of the code, here's what breaks if you change `CaseInsensitiveDict.__setitem__`:

## Core Functionality

**`__setitem__` is critical because it maintains the case-insensitive lookup invariant:**

```python
def __setitem__(self, key: str, value: _VT) -> None:
    self._store[key.lower()] = (key, value)  # stores tuple: (original_case_key, value)
```

The method stores a **tuple of (original_cased_key, value)** keyed by the **lowercased key**. This enables:

### 1. **Case-insensitive lookups** (`__getitem__`, `__contains__`)
If you break `__setitem__`, these won't find values because they depend on the tuple structure:
```python
def __getitem__(self, key: str) -> _VT:
    return self._store[key.lower()][1]  # retrieves tuple, gets [1] (the value)
```

### 2. **Case preservation in iteration** (`__iter__`)
Returns the **original cased key** from the tuple:
```python
def __iter__(self) -> Iterator[str]:
    return (casedkey for casedkey, _ in self._store.values())
```
Without storing the original key in `__setitem__`, all keys would be lowercased when iterating.

### 3. **The `copy()` method**
```python
def copy(self) -> CaseInsensitiveDict[_VT]:
    return CaseInsensitiveDict(self._store.values())  # passes tuples to __init__
```
Constructor calls `update()` → `__setitem__()`, so it depends on the tuple format.

### 4. **Equality comparison** (`__eq__`)
Uses `lower_items()` which iterates `_store.items()` and expects the tuple format.

## Real-world Impact

These are HTTP headers used in **requests**:
- **Sessions** set default headers via `ses.headers["Accept-Encoding"] = "gzip"`
- **Responses** initialize from HTTP via `CaseInsensitiveDict(getattr(resp, "headers", {}))`
- **PreparedRequests** build headers via `self.headers["Content-Length"] = "0"`

Breaking `__setitem__` breaks:
- Reading headers case-insensitively (`response.headers["content-encoding"]`)
- Preserving original header casing in requests
- All header-merging operations in sessions
- Test assertions that check `r.headers["Location"]`
