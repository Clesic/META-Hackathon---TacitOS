"""Local Missing Monday rehearsal. Meta diagnoses a stall; it does not grade the case."""
from __future__ import annotations

import argparse
import json
import logging
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from app.model import BUDGET_USD, ModelError, runtime
from app.store import ROOT, Store

log = logging.getLogger('missingmonday.server')
STATIC = ROOT / 'app' / 'static'
ASSETS = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/app.css': ('app.css', 'text/css; charset=utf-8'),
    '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
}
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
}


def session_header(headers) -> str | None:
    sid = headers.get('X-Session-ID')
    if sid is not None and (len(sid) > 200 or '\r' in sid or '\n' in sid):
        raise ValueError('Invalid session.')
    return sid


def handler(store: Store, port: int):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def _safe_path(self) -> str:
            path = urlsplit(self.path).path.replace('\r', '').replace('\n', '')
            return path[:200] or '/'

        def send(self, status: int, data, kind: str = 'application/json; charset=utf-8') -> None:
            raw = data if isinstance(data, (bytes, bytearray)) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(raw)
            elapsed = int((time.perf_counter() - getattr(self, '_started', time.perf_counter())) * 1000)
            log.info('%s %s %s %dms', self.command, self._safe_path(), status, elapsed)

        def valid_host(self) -> bool:
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def do_GET(self) -> None:
            self._started = time.perf_counter()
            if not self.valid_host():
                return self.send(403, {'error': 'Local access only.'})
            path = urlsplit(self.path).path
            if path == '/health':
                conf = runtime()
                return self.send(200, {
                    'status': 'ok',
                    'model': 'ready' if conf['key'] else 'not_configured',
                    'provider': conf['provider'],
                    'model_name': conf['model'],
                    'budget_usd': BUDGET_USD,
                    'spent_usd': store.spent(),
                })
            if path == '/api/state':
                try:
                    return self.send(200, store.state(session_header(self.headers)))
                except LookupError as exc:
                    return self.send(404, {'error': str(exc)})
                except ValueError as exc:
                    return self.send(400, {'error': str(exc)})
            if path not in ASSETS:
                return self.send(404, {'error': 'Not found.'})
            name, asset_type = ASSETS[path]
            self.send(200, (STATIC / name).read_bytes(), asset_type)

        def do_POST(self) -> None:
            self._started = time.perf_counter()
            if not self.valid_host():
                return self.send(403, {'error': 'Local access only.'})
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}'):
                return self.send(403, {'error': 'Cross-origin request blocked.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'JSON required.'})
            try:
                sid = session_header(self.headers)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 10000:
                    raise ValueError('Invalid request size.')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or len(body) > 12:
                    raise ValueError('JSON object required.')
                path = urlsplit(self.path).path
                if path == '/api/sessions':
                    return self.send(201, {'session_id': store.create()})
                if path == '/api/attempts':
                    return self.send(201, {'attempt_id': store.start(sid, body.get('case_id'))})
                if path == '/api/inspect':
                    return self.send(200, store.inspect(sid, body.get('attempt_id'), body.get('evidence_id')))
                if path == '/api/actions':
                    store.record(sid, body.get('attempt_id'), body.get('id'), body.get('action'), body.get('reason'), body.get('evidence_refs', []), body.get('category', 'knowledge'))
                    return self.send(200, {'saved': True})
                if path == '/api/guidance':
                    return self.send(200, store.review(sid, body.get('attempt_id'), body.get('answer'), body.get('decision')))
                if path == '/api/diagnose':
                    return self.send(200, store.diagnose(sid, body.get('attempt_id')))
                if path == '/api/draft':
                    return self.send(200, store.draft_card(sid, body.get('attempt_id'), body.get('answer')))
                if path == '/api/suggest':
                    return self.send(200, store.suggest(sid, body.get('attempt_id')))
                if path == '/api/attack':
                    return self.send(200, store.attack(sid))
                return self.send(404, {'error': 'Not found.'})
            except LookupError as exc:
                self.send(404, {'error': str(exc)})
            except ModelError as exc:
                log.warning('model error on %s: %s', self._safe_path(), exc)
                self.send(502, {'error': str(exc)})
            except json.JSONDecodeError:
                self.send(400, {'error': 'Invalid JSON.'})
            except (ValueError, TypeError) as exc:
                log.info('rejected %s: %s', self._safe_path(), exc)
                self.send(400, {'error': str(exc)})
            except Exception:
                log.exception('unhandled error on %s', self._safe_path())
                self.send(500, {'error': 'Could not save this request. Please retry.'})

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--db', default=str(ROOT / 'runs' / 'missing-monday.sqlite3'))
    args = parser.parse_args()
    store = Store(args.db)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(store, args.port))
    print(f'Missing Monday: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
