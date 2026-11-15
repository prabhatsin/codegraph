# Text.truncate (grep, run 2)

Based on a search of the codebase, here's what depends on `Text.truncate()`:

## Direct Dependencies

**Core rendering components:**
- **`rich/rule.py`** — truncates rule titles (4+ calls) and rule lines to fit the console width
- **`rich/panel.py`** — truncates text headers to fit within panel width
- **`rich/containers.py`** — truncates lines during justification (left/center/right/full align)

**Text module internals:**
- **`Text.justify()`** (line 940) — uses truncate as part of alignment
- **`Text.wrap()`** (line 1232) — uses truncate during line wrapping

## Tests
- **`tests/test_text.py`** — tests for truncate with ellipsis and padding behavior (at least 2 test functions)

## What Could Break

If you change `Text.truncate()`, here's the blast radius:

1. **Signature changes** (params added/removed/reordered) → all callers break unless they use keyword arguments (most do use `overflow=` and `pad=`)
2. **Behavior changes** (how it handles overflow, padding, or width calculation) → visual regressions in rules, panels, and justified text throughout the TUI
3. **Return value changes** (currently returns `None`) → if callers expect something returned, they'd break
4. **Cell width calculation** — any change to how it respects wide characters (CJK, emoji) would break layout in international UIs

**Most risky**: changes to the overflow logic or how `pad=True` works, since those affect visual output in Panel titles and Rules directly visible to users.
