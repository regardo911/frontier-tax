#!/usr/bin/env python3
"""logproxy.py - sit between a tool and its provider, log every call. Chapter 4.

Run:  UPSTREAM=https://api.provider.example python3 logproxy.py
      (listens on 127.0.0.1:8777)
Then point your tool's base URL at http://127.0.0.1:8777

Two limits, both real. It does not handle streaming responses, which most
interactive tools use by default - turn streaming off in the tool, or extend
do_POST to accumulate server-sent events before logging. And it terminates TLS
on your machine, so keep it bound to 127.0.0.1 and never expose it.
"""
import json, os, sys, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

# the book runs everything from one flat directory. this repo lays the files
# out by chapter, so put the sibling chapter folders on the path. copy this
# file into a flat directory on its own and you can delete these three lines.
_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tracelog import normalize_usage, price, TRACE_PATH

UPSTREAM = os.environ["UPSTREAM"]        # e.g. https://api.provider.example
TASK     = os.environ.get("TASK", "agent-step")
HOP = {"host", "content-length", "connection", "transfer-encoding"}

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        req = urllib.request.Request(UPSTREAM + self.path, data=body,
                                     headers=headers, method="POST")
        t0 = time.perf_counter()
        with urllib.request.urlopen(req) as up:
            raw, status = up.read(), up.status
        ms = int((time.perf_counter() - t0) * 1000)

        try:
            sent = json.loads(body)
            got  = json.loads(raw)
            usage = normalize_usage(got.get("usage"))
            model = got.get("model") or sent.get("model", "unknown")
            try:
                cost = price(model, usage)
            except KeyError:
                cost = None
            with open(TRACE_PATH, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(), "model": model, "task": TASK, "ms": ms,
                    "ok": status == 200, "error": None, "cost_usd": cost,
                    "input": json.dumps(sent.get("messages", ""))[:20000],
                    "output": json.dumps(got.get("content")
                                         or got.get("choices", ""))[:20000],
                    **usage}) + "\n")
        except Exception as e:                 # never break the caller
            print("[logproxy] not logged:", e)

        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):                 # quiet
        pass

if __name__ == "__main__":
    print(f"logproxy -> {UPSTREAM}  writing {TRACE_PATH}")
    HTTPServer(("127.0.0.1", 8777), Handler).serve_forever()
