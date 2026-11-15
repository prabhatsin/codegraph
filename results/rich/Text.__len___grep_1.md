# Text.__len__ (grep, run 1)

Perfect! The agent found comprehensive results. Here's the complete picture:

## **What Breaks if You Change `Text.__len__`**

Changing `Text.__len__()` would break **15 locations across 7 files**:

### **Critical Internal Operations in text.py:**
- **`append()` method** (lines 984, 991) — Uses `len(text)` to calculate span offsets when appending other Text objects
- **`append_text()` method** (lines 1007, 1013) — Uses `len(text)` to track cumulative text length for span positions
- **`join()` method** (lines 796, 801) — Uses `len(text)` to accumulate offsets when joining multiple Text objects
- **`append()` validation** (line 966) — Checks `if len(text):` for conditional logic
- Plus the 6 methods I identified earlier: `stylize()`, `stylize_before()`, `style_at()`, `extend_style()`, `set_length()`, `rstrip()`

### **Dependent Code in Other Modules:**
- **`rich/markup.py`** (lines 215, 219, 223, 225) — Uses `len(text)` extensively during markup rendering to calculate span boundaries
- **`rich/_log_render.py`** (line 63) — Uses `len(text)` to calculate padding spaces for log output
- **`examples/rainbow.py`** (line 15) — Uses `len(text)` to iterate with `range(len(text))`

### **Direct Test:**
- **`tests/test_text.py`** (line 35) — Explicit test: `assert len(Text("foo")) == 3`

## **The Invariant**
Every usage assumes `len(Text(...))` returns the **character count** of the plain text. If you changed it to return cell width, byte length, or span count, you'd break:
- Span offset calculations (corrupting all styling)
- Text padding/cropping operations
- Markup rendering
- Any code iterating over text length

The character count is the foundational contract for the entire Text class.
