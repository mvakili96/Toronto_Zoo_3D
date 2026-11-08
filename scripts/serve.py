"""Serve only public assets, never the multi-GB source directories."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
import argparse

if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8000);args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]/'public'
    class Handler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control','no-cache')
            super().end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(root)))
    print(f'Toronto Zoo explorer: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
