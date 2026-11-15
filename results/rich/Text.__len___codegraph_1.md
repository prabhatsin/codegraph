# Text.__len__ (codegraph, run 1)

Here's what breaks if you change `Text.__len__`:

**Direct callers (1 hop — immediate impact):**
- `Text.append`, `Text.append_text`, `Text.append_tokens` — internal Text methods that track position
- `Text.join`, `Text.rstrip_end`, `Text.stylize`, `Text.stylize_before` — text manipulation methods
- `LogRender.__call__` — log rendering
- `Traceback._render_syntax_error` — traceback display
- `markup.render` — markup parsing

**Indirect callers (2 hops — downstream impact):**
A large surface area including:
- **Text methods**: `__add__`, `__rich_console__`, `apply_meta`, `assemble`, `from_ansi`, `from_markup`, `on`, `styled`, `with_indent_guides`, `wrap`
- **Console rendering**: `Console._collect_renderables`, `Console.log`, `Console.render_str`, `group`
- **Layout components**: `Panel.__rich_console__`, `Rule.__rich_console__`
- **Markdown**: `TextElement.on_text`, `TableElement.__rich_console__`, `TableDataElement.on_text`, `ImageItem.__rich_console__`
- **Syntax highlighting**: `Syntax.highlight`, `Syntax._get_syntax`, `Syntax._apply_stylized_ranges`
- **Other utilities**: `AnsiDecoder.decode_line`, `Inspect._get_signature`, `Inspect._render`, `FileProxy.write`

**Summary:** The most critical are the 1-hop callers (particularly `Text.append*`, `Text.stylize*`, and `Text.join`) since they directly depend on `__len__` for position tracking. Any change to `__len__` would propagate through text manipulation and rendering throughout the entire console output system.
