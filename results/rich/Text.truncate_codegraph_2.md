# Text.truncate (codegraph, run 2)

Changing `Text.truncate` would break these direct dependents (1 hop):

- **`rich/containers.py::Lines.justify`** (line 98)
- **`rich/panel.py::Panel.__rich_console__`** (line 141)
- **`rich/rule.py::Rule.__rich_console__`** (line 47)
- **`rich/rule.py::Rule._rule_line`** (line 103)
- **`rich/text.py::Text.align`** (line 932)
- **`rich/text.py::Text.wrap`** (line 1185)

And indirectly (2 hops):
- **`rich/console.py::Console.render`** (line 1288)
- **`rich/text.py::Text.__rich_console__`** (line 677)

The most critical areas are **Panel, Rule, and Text alignment/wrapping** — these are high-level rendering components that depend on truncation behavior. Changes to the signature or behavior of `Text.truncate` would likely impact text rendering throughout the library.
