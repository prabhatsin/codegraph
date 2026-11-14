"""Ground truth: run real requests code and record which function calls which."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SRC = Path("../sample_repo/src").resolve()
sys.path.insert(0, str(SRC))
import requests  # noqa: E402  (the repo's own copy, not a pip install)


# ---------- a tiny local server, so no internet is needed ----------
class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body=b"{}", headers=()):
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/redirect"):
            self.reply(302, b"", [("Location", "/ok")])
        elif self.path.startswith("/auth") and "Authorization" not in self.headers:
            self.reply(401, b"", [("WWW-Authenticate", 'Basic realm="x"')])
        elif self.path.startswith("/missing"):
            self.reply(404)
        else:
            self.reply(200, b'{"ok": true}', [("Set-Cookie", "sid=abc"),
                                              ("Content-Type", "application/json")])

    do_POST = do_PUT = do_DELETE = do_PATCH = do_GET

    def do_HEAD(self):
        self.reply(200, b"")

    def log_message(self, *args):
        pass


server = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{server.server_port}"


# ---------- record every requests -> requests call ----------
edges = set()


def key_of(frame):
    path = Path(frame.f_code.co_filename)
    if SRC not in path.parents:
        return None
    qual = frame.f_code.co_qualname.split(".<locals>")[0]  # fold nested helpers
    return f"{path.relative_to(SRC)}::{qual}"


def profiler(frame, event, arg):
    if event == "call":
        callee, caller = key_of(frame), frame.f_back and key_of(frame.f_back)
        if callee and caller and callee != caller:
            edges.add((caller, callee))


def scenarios():
    requests.get(URL + "/ok", params={"q": "1"}).json()
    requests.post(URL + "/ok", json={"a": 1})
    requests.put(URL + "/ok", data="x")
    requests.patch(URL + "/ok", data={"a": "b"})
    requests.delete(URL + "/ok")
    requests.head(URL + "/ok")
    requests.options(URL + "/ok")
    requests.get(URL + "/redirect")
    requests.get(URL + "/auth", auth=("user", "pass"))
    with requests.Session() as s:
        s.get(URL + "/ok", headers={"X-Test": "1"}, cookies={"a": "b"})
        s.get(URL + "/ok").content
    r = requests.get(URL + "/missing")
    try:
        r.raise_for_status()
    except requests.HTTPError:
        pass


sys.setprofile(profiler)
scenarios()
sys.setprofile(None)

Path("trace_edges.json").write_text(json.dumps(sorted(edges), indent=1))
print("traced call edges:", len(edges))
print("functions seen   :", len({k for e in edges for k in e}))