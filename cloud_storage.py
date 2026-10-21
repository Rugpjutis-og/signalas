"""Private Neon snapshot archive. No browser-facing database API or credentials."""
import hashlib
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudStorageError(ValueError):
    pass


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS signalas_fetches (
        scope text NOT NULL, snapshot_id text NOT NULL,
        collected_at timestamptz NOT NULL, packet jsonb NOT NULL,
        PRIMARY KEY(scope, snapshot_id))""",
    """CREATE TABLE IF NOT EXISTS signalas_content (
        scope text NOT NULL, source text NOT NULL, content_id text NOT NULL,
        collected_at timestamptz NOT NULL, payload jsonb NOT NULL,
        PRIMARY KEY(scope, source, content_id))""",
]


def endpoint(connection):
    try:
        u = urlsplit(connection)
        host = u.hostname or ''
        valid = (u.scheme in ('postgres', 'postgresql') and u.username and u.password
                 and u.path.strip('/') and u.port in (None, 5432)
                 and re.fullmatch(r'ep-[a-z0-9-]+\.[a-z0-9.-]+\.neon\.tech', host)
                 and not u.fragment)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise CloudStorageError('Netinkama Neon duomenų bazės konfigūracija.')
    return 'https://api.' + host.split('.', 1)[1] + '/sql'


def query(connection, queries):
    url = endpoint(connection)
    request = Request(url, data=json.dumps({'queries': queries}).encode(), headers={
        'Content-Type': 'application/json', 'Neon-Connection-String': connection,
        'Neon-Array-Mode': 'true', 'Neon-Raw-Text-Output': 'true',
    }, method='POST')
    try:
        # Redirects must never forward the connection credential to another host.
        with build_opener(NoRedirect()).open(request, timeout=45) as response:
            return json.load(response)
    except Exception:
        # Provider errors may echo credentials, SQL parameters or private content.
        raise CloudStorageError('Nepavyko įrašyti į debesijos duomenų bazę; vietinė kopija išsaugota.') from None


def sync(packet, connection, scope):
    if not isinstance(packet.get('records'), list) or not packet.get('collected_at') or not scope:
        raise CloudStorageError('Trūksta surinkimo duomenų arba šaltinio identifikatoriaus.')
    body = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    snapshot = hashlib.sha256(body.encode()).hexdigest()
    query(connection, [{'query': sql, 'params': []} for sql in SCHEMA])
    # Both writes are one transaction: retries cannot duplicate snapshots/content.
    result = query(connection, [
        {'query': """INSERT INTO signalas_fetches(scope,snapshot_id,collected_at,packet)
            VALUES($1,$2,$3::timestamptz,$4::jsonb) ON CONFLICT DO NOTHING""",
         'params': [scope, snapshot, packet['collected_at'], body]},
        {'query': """INSERT INTO signalas_content(scope,source,content_id,collected_at,payload)
            SELECT $1, COALESCE(r->>'source','diaspora'), r->>'id', $2::timestamptz, r
            FROM jsonb_array_elements($3::jsonb->'records') r
            ON CONFLICT(scope,source,content_id) DO UPDATE
            SET collected_at=EXCLUDED.collected_at,payload=EXCLUDED.payload
            WHERE EXCLUDED.collected_at >= signalas_content.collected_at""",
         'params': [scope, packet['collected_at'], body]},
    ])
    if len(result.get('results', [])) != 2:
        raise CloudStorageError('Debesijos įrašymo patvirtinimas negautas.')
    return {'status': 'ok', 'records': len(packet['records']), 'collected_at': packet['collected_at']}


def account_scope(config):
    identity = config.get('DIASPORA_BASE_URL', 'https://diaspora.sauliai.lt').rstrip('/') + '\n' + config.get('DIASPORA_USERNAME', '')
    return hashlib.sha256(identity.encode()).hexdigest()


if __name__ == '__main__':
    from integration_config import ROOT, settings
    config = settings()
    try:
        packet = json.loads((ROOT / 'var/diaspora-latest.json').read_text())
        print(json.dumps(sync(packet, config.get('SIGNALAS_DATABASE_URL'), account_scope(config))))
    except (CloudStorageError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'error', 'message': str(error) if isinstance(error, CloudStorageError) else 'Vietinė imtis neprieinama.'}))
        raise SystemExit(1)
