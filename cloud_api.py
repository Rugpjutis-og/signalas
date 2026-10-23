"""Authenticated Vercel API. All application persistence is in Neon."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from cloud_repository import Repository
import live_data

COOKIE = '__Host-signalas-session'


def signature(value, password):
    return hmac.new(password.encode(), value.encode(), hashlib.sha256).hexdigest()


def session_token(password, now=None):
    value = str(int(now or time.time()) + 43200) + '.' + secrets.token_hex(16)
    return value + '.' + signature(value, password)


def valid_session(token, password, now=None):
    try:
        expires, nonce, signed = token.split('.')
        value = expires + '.' + nonce
        return int(now or time.time()) < int(expires) <= int(now or time.time()) + 43200 and hmac.compare_digest(signed, signature(value, password))
    except (ValueError, TypeError, AttributeError):
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log request bodies, private source content or credentials.

    def send(self, value, status=200, cookie=None, mime='application/json; charset=utf-8'):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'private, no-store')
        self.send_header('Vary', 'Cookie')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def route(self):
        url = urlsplit(self.path)
        args = parse_qs(url.query, keep_blank_values=True)
        return ('/api/' + args['route'][0].strip('/') if 'route' in args else url.path), args

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        password = os.environ.get('SIGNALAS_ACCESS_PASSWORD', '')
        if len(password) < 16:
            self.send({'error': 'Vercel aplinkoje reikia nustatyti SIGNALAS_ACCESS_PASSWORD (bent 16 ženklų).', 'configured': False, 'reason': 'access_password_missing' if not password else 'access_password_too_short'}, 503)
            return
        route, args = self.route()
        if route == '/api/background/tick':
            if method != 'GET':
                self.send({'error': 'Neleistinas metodas.'}, 405)
                return
            from background_auth import verified_claims
            if not verified_claims(self.headers.get('Authorization', '')):
                self.send({'error': 'Prieiga atmesta.'}, 401)
                return
            try:
                from background_tick import tick
                repository = Repository(dict(os.environ))
                repository.initialize()
                self.send(tick(repository))
            except Exception:
                self.send({'error': 'Foninis vykdymas nepavyko.'}, 502)
            return
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            token = cookies[COOKIE].value if COOKIE in cookies else ''
        except Exception:
            token = ''
        authenticated = valid_session(token, password)
        csrf = signature('csrf:' + token, password) if authenticated else None
        if method == 'POST':
            origins = {'https://signalas-ecru.vercel.app'}
            if os.environ.get('VERCEL_URL'):
                origins.add('https://' + os.environ['VERCEL_URL'])
            if self.headers.get('Origin') not in origins:
                self.send({'error': 'Užklausa atmesta.'}, 403)
                return
        if route == '/api/auth/session' and method == 'GET':
            self.send({'configured': True, 'authenticated': authenticated, 'csrf': csrf})
            return
        if not (route == '/api/auth/login' and method == 'POST') and not authenticated:
            self.send({'error': 'Prisijunkite prie Signalas.'}, 401)
            return
        if method == 'POST' and route != '/api/auth/login' and not hmac.compare_digest(self.headers.get('X-Signalas-CSRF', ''), csrf or 'invalid'):
            self.send({'error': 'Užklausa atmesta.'}, 403)
            return
        try:
            repository = Repository(dict(os.environ))
            repository.initialize()
            payload = {}
            if method == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 100000:
                    raise ValueError('Netinkamas užklausos dydis.')
                payload = json.loads(self.rfile.read(size)) if size else {}
                if not isinstance(payload, dict):
                    raise ValueError('Reikia JSON objekto.')
            if route == '/api/auth/login' and method == 'POST':
                # Database rate limit works across cold starts; IPs are never stored directly.
                address = (self.headers.get('X-Forwarded-For') or 'unknown').split(',')[0].strip()
                identity = signature('login:' + address, password)
                attempts = repository.sql('''INSERT INTO signalas_login_attempts(identity,attempts,expires_at)
                    VALUES($1,1,now()+interval '15 minutes') ON CONFLICT(identity) DO UPDATE
                    SET attempts=CASE WHEN signalas_login_attempts.expires_at<now() THEN 1 ELSE signalas_login_attempts.attempts+1 END,
                    expires_at=CASE WHEN signalas_login_attempts.expires_at<now() THEN now()+interval '15 minutes' ELSE signalas_login_attempts.expires_at END
                    RETURNING attempts''', [identity])['rows']
                if int(attempts[0][0]) > 10:
                    self.send({'error': 'Per daug bandymų. Bandykite po 15 minučių.'}, 429)
                    return
                supplied = payload.get('password')
                if not isinstance(supplied, str) or not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(), hashlib.sha256(password.encode()).digest()):
                    self.send({'error': 'Neteisingas prieigos slaptažodis.'}, 401)
                    return
                token = session_token(password)
                self.send({'authenticated': True, 'csrf': signature('csrf:' + token, password)}, cookie=COOKIE+'='+token+'; Path=/; Secure; HttpOnly; SameSite=Strict')
                return
            if route == '/api/auth/logout' and method == 'POST':
                self.send({'status': 'ok'}, cookie=COOKIE+'=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0')
            elif route == '/api/dashboard/bootstrap' and method == 'GET':
                self.send(dict(live_data.bootstrap(repository), csrf=csrf))
            elif route == '/api/dashboard/context':
                if method == 'POST':
                    repository.save_context(payload.get('context'))
                self.send({'context': repository.read('live-context.json')})
            elif route == '/api/dashboard/period' and method == 'POST':
                live_data.store_period(payload['end_date'], repository, start_date=payload['start_date'])
                self.send(live_data.bootstrap(repository))
            elif route == '/api/collection/status' and method == 'GET':
                self.send({'available': bool(repository.config.get('DIASPORA_PASSWORD') and repository.config.get('DIASPORA_USERNAME')), 'csrf': csrf,
                           'message': 'Vercel aplinkoje dar trūksta Diasporos prisijungimo nustatymų.'})
            elif route == '/api/collection/refresh' and method == 'POST':
                self.send(repository.collect())
            elif route == '/api/analysis/status' and method == 'GET':
                self.send(repository.read('analysis-job.json', {}) or {'status': 'idle', 'remaining': 0})
            elif route == '/api/analysis/continue' and method == 'POST':
                from cloud_analysis import step
                self.send(step(repository))
            elif route == '/api/monitoring/status' and method == 'GET':
                self.send(repository.monitoring_status())
            elif route == '/api/metrics/context' and method == 'GET':
                from metrics import metrics_context
                self.send(metrics_context())
            elif route in ('/api/platform/overview', '/api/thermometer') and method == 'GET':
                params = {'start_date': args.get('start_date', [None])[0], 'end_date': args.get('end_date', [None])[0]}
                fn = live_data.platform if route == '/api/platform/overview' else live_data.thermometer
                self.send(fn(root=repository, **params))
            elif route == '/api/media/image' and method == 'GET':
                from private_media import MediaDelivery
                data, mime = MediaDelivery(root=repository, config=lambda: dict(os.environ)).image(args['source'][0], args['id'][0], int(args['index'][0]))
                self.send(data, mime=mime)
            else:
                self.send({'error': 'Nerastas API kelias.'}, 404)
        except (ValueError, KeyError, TypeError, OverflowError):
            self.send({'error': 'Užklausos įvykdyti nepavyko. Patikrinkite duomenis ir Vercel konfigūraciją; paskutinė kopija išsaugota.'}, 400)
        except Exception:
            self.send({'error': 'Ryšys su duomenų šaltiniu arba duomenų baze nepavyko. Paskutinė kopija išsaugota.'}, 502)
