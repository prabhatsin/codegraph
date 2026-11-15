# Text.__len__ (codegraph, run 2)

Here's what would break if you change `Text.__len__`:

## Direct callers (1 hop) — most critical:
- **`Text.append()`** — uses `len(self)` to calculate offsets for span placement
- **`Text.append_text()`** — same offset calculation for appending Text instances  
- **`Text.append_tokens()`** — calculates offsets for token spans
- **`Text.stylize()` / `Text.stylize_before()`** — uses `len(self)` for boundary validation and negative index handling
- **`Text.rstrip_end()`** — compares `len(self)` to determine excess content
- **`Text.join()`** — uses `len(text)` to accumulate offsets when joining multiple Text objects
- **`LogRender.__call__()`** — uses `len()` to create padding: `Text(" " * len(log_time_display))`
- **`markup.render()`** — unknown context but processing Text markup

## Secondary callers (2 hops) — cascade effects:
About 20 additional functions would be affected indirectly through the direct callers, including:
- `Text.__add__()`, `Text.__rich_console__()`, `Text.wrap()`, `Text.styled()`
- Console rendering functions (`Console.log()`, `Console.render_str()`)
- Traceback, syntax highlighting, markdown, and panel rendering

## The core issue:
`Text.__len__` currently returns `self._length` (a cached integer). **If you change what it returns, any code relying on it for offset calculations, span bounds, or padding will produce incorrect results**. The most fragile areas are offset-based operations where span positioning depends on accurate length values.

What are you considering changing about it?
