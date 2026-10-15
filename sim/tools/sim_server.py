"""Local helper server for recording the track simulator.

Serves the project folder (like `python -m http.server`) and accepts POST /save/<name> to write
the request body to sim/results/capture/<name>. The browser uses this to save animation frames
and result JSON from the real simulator, which make_presentation_assets.py turns into GIFs and charts.
Only binds to 127.0.0.1.

Usage: python sim/tools/sim_server.py [port]      (default 8766)
"""
import http.server
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'sim', 'results', 'capture')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_POST(self):
        m = re.fullmatch(r'/save/([A-Za-z0-9_\-./]+)', self.path)
        if not m or '..' in m.group(1):
            self.send_error(400, 'bad name')
            return
        path = os.path.join(OUT, m.group(1))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        n = int(self.headers.get('Content-Length', 0))
        with open(path, 'wb') as fh:
            fh.write(self.rfile.read(n))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    os.makedirs(OUT, exist_ok=True)
    print(f'serving {ROOT} on http://127.0.0.1:{port} (POST /save/<name> -> {OUT})')
    http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
