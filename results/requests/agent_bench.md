# Claude Code (haiku): codegraph vs grep

| Question | Mode | Run | Cost | API time | Turns | Output tokens | Found | Missed |
|---|---|---|---|---|---|---|---|---|
| `Session.send` | codegraph | 1 | $0.0147 | 8s | 4 | 679 | 3/3 | - |
| `Session.send` | codegraph | 2 | $0.0159 | 9s | 4 | 884 | 3/3 | - |
| `Session.send` | grep | 1 | $0.0541 | 19s | 5 | 1713 | 2/3 | request |
| `Session.send` | grep | 2 | $0.0337 | 19s | 9 | 1883 | 2/3 | request |
| `merge_cookies` | codegraph | 1 | $0.0238 | 13s | 5 | 1155 | 3/3 | - |
| `merge_cookies` | codegraph | 2 | $0.0147 | 8s | 4 | 754 | 3/3 | - |
| `merge_cookies` | grep | 1 | $0.0513 | 13s | 4 | 1348 | 2/3 | Session.request |
| `merge_cookies` | grep | 2 | $0.0179 | 13s | 7 | 1552 | 1/3 | Session.prepare_request, Session.request |
| `CaseInsensitiveDict.__setitem__` | codegraph | 1 | $0.0165 | 9s | 4 | 1002 | 3/3 | - |
| `CaseInsensitiveDict.__setitem__` | codegraph | 2 | $0.0175 | 10s | 4 | 1033 | 3/3 | - |
| `CaseInsensitiveDict.__setitem__` | grep | 1 | $0.0393 | 18s | 8 | 1574 | 0/3 | PreparedRequest.prepare_headers, PreparedRequest.prepare_body, PreparedRequest.prepare_content_length |
| `CaseInsensitiveDict.__setitem__` | grep | 2 | $0.0326 | 21s | 6 | 1855 | 0/3 | PreparedRequest.prepare_headers, PreparedRequest.prepare_body, PreparedRequest.prepare_content_length |

| Mode | Total cost | Total API time | Callers found |
|---|---|---|---|
| codegraph | $0.1031 | 57s | 18/18 |
| grep | $0.2290 | 103s | 7/18 |
