# Text.__len__ (grep, run 2)

Here's what would break if you change `Text.__len__`:

## Critical Breakage

**1. Span/Style Management (most critical)**
- The `stylize()` and `stylize_before()` methods (lines 459, 485) rely on `len(self)` for:
  - Converting negative indices to positive offsets
  - Validating that styles are applied within text bounds
  - If `__len__` returns the wrong value, spans will be indexed incorrectly

**2. Text Slicing and Division**
- `divide()` method (line 1105) uses `len(text)` to compute divide offsets for splitting text into lines
- `__getitem__` (line 203) uses `len(self.plain)` for slice validation—changing `__len__` would be inconsistent
- Incorrect divisions would corrupt span ranges across multiple lines

**3. Offset Calculations**
- Negative indexing in `get_style_at_offset()` (line 552): `offset = len(self) + offset` 
- If `len()` returns wrong value, style lookups fail at negative offsets

**4. Right-cropping and Suffix Removal**
- `right_crop()` method (line 1171) uses `len(self.plain)` to compute the cutoff point
- `remove_suffix()` (line 538) uses `len(suffix)` not `len(self)`, but relies on correct cropping
- Removing characters from the end would use wrong boundaries if `__len__` is inconsistent

## State Sync Issues

The `_length` cache gets updated in many places (lines 153, 403-404, 577, 844, 872, 974, 981, 991, 1005, 1013, 1035, 1183). If `__len__` returns something other than `self._length`:
- Text operations like `extend_style()` increment `_length` but `len()` would return different values
- Spans would be indexed against mismatched boundaries
- The `__bool__` method (line 159) relies on truthiness of `self._length`

## Test Failures
- Direct assertions like `assert len(Text("foo")) == 3` would fail

**Bottom line:** `__len__` must return the character count of plain text (`self._length`). Any deviation breaks span management, slicing, negative indexing, and style application throughout the Text class.
