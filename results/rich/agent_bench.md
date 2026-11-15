# Claude Code (haiku): codegraph vs grep

| Question | Mode | Run | Cost | API time | Turns | Output tokens | Found | Missed |
|---|---|---|---|---|---|---|---|---|
| `Text.truncate` | codegraph | 1 | $0.0590 | 9s | 4 | 816 | 3/3 | - |
| `Text.truncate` | codegraph | 2 | $0.0158 | 8s | 4 | 915 | 3/3 | - |
| `Text.truncate` | grep | 1 | $0.0436 | 20s | 8 | 1797 | 3/3 | - |
| `Text.truncate` | grep | 2 | $0.0278 | 15s | 6 | 1426 | 2/3 | Panel.__rich_console__ |
| `Style.__add__` | codegraph | 1 | $0.0271 | 12s | 4 | 1379 | 3/3 | - |
| `Style.__add__` | codegraph | 2 | $0.0164 | 10s | 3 | 1082 | 3/3 | - |
| `Style.__add__` | grep | 1 | $0.0709 | 31s | 11 | 2811 | 1/3 | Style.combine, Style.chain |
| `Style.__add__` | grep | 2 | $0.0646 | 31s | 17 | 2961 | 0/3 | Style.combine, Style.chain, Table.get_row_style |
| `Text.__len__` | codegraph | 1 | $0.0270 | 11s | 4 | 1087 | 3/3 | - |
| `Text.__len__` | codegraph | 2 | $0.0287 | 14s | 5 | 1193 | 3/3 | - |
| `Text.__len__` | grep | 1 | $0.3342 | 149s | 1 | 718 | 3/3 | - |
| `Text.__len__` | grep | 2 | $0.0696 | 37s | 19 | 3669 | 1/3 | Text.append, Text.join |

| Mode | Total cost | Total API time | Callers found |
|---|---|---|---|
| codegraph | $0.1740 | 65s | 18/18 |
| grep | $0.6107 | 282s | 10/18 |
