"""Neon-backed application state and read adapter; never writes local files."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cloud_storage import query, account_scope, sync, SCHEMA as FETCH_SCHEMA
from integration_config import ROOT

SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS signalas_state (
        scope text NOT NULL, name text NOT NULL, value jsonb NOT NULL,
        PRIMARY KEY(scope,name))''',
    '''CREATE TABLE IF NOT EXISTS signalas_jobs (
        scope text PRIMARY KEY, owner text NOT NULL, expires_at timestamptz NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS signalas_login_attempts (
        identity text PRIMARY KEY, attempts integer NOT NULL, expires_at timestamptz NOT NULL)''',
]


class Repository:
    def __init__(self, config):
        self.config = config
        self.connection = config.get('DATABASE_URL') or config.get('SIGNALAS_DATABASE_URL')
        self.scope = account_scope(config)
        self.values = {}
        self.packet = None

    def sql(self, statement, params=None):
        return query(self.connection, [{'query': statement, 'params': params or []}])['results'][0]

    def initialize(self):
        query(self.connection, [{'query': sql, 'params': []} for sql in FETCH_SCHEMA + SCHEMA])

    def read(self, name, default=None):
        if name not in self.values:
            rows = self.sql('SELECT value FROM signalas_state WHERE scope=$1 AND name=$2', [self.scope, name])['rows']
            self.values[name] = json.loads(rows[0][0]) if rows else default
        return self.values[name]

    def write(self, name, value):
        self.sql('''INSERT INTO signalas_state(scope,name,value) VALUES($1,$2,$3::jsonb)
            ON CONFLICT(scope,name) DO UPDATE SET value=EXCLUDED.value''', [self.scope, name, json.dumps(value)])
        self.values[name] = value

    def save_context(self, value):
        from openai_analysis import context_data
        value = context_data(value)
        if value is None:
            raise ValueError('Užpildykite abu pradinio konteksto laukus.')
        rows = self.sql('''INSERT INTO signalas_state(scope,name,value) VALUES($1,'live-context.json',$2::jsonb)
            ON CONFLICT DO NOTHING RETURNING value''', [self.scope, json.dumps(value)])['rows']
        self.values.pop('live-context.json', None)
        current = self.read('live-context.json')
        if not rows and current != value:
            raise ValueError('Pradinis kontekstas jau išsaugotas. Pratybų metu jo keisti negalima.')
        return current

    def latest(self):
        if self.packet is None:
            rows = self.sql('SELECT packet FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1', [self.scope])['rows']
            self.packet = json.loads(rows[0][0]) if rows else {
                'records': [], 'source': 'diaspora.sauliai.lt', 'collected_at': None,
                'coverage': 'account_stream_and_own_profile', 'stream_complete': False}
        return self.packet

    def __truediv__(self, name):
        return CloudPath(self, name) if name.startswith('var') else ROOT / name

    def monitoring_status(self, **kwargs):
        packet = self.latest()
        failure = self.read('collection-status.json', {}) or {}
        reason = 'collection_failed' if failure.get('status') == 'error' else None
        if not packet.get('collected_at'):
            reason = reason or 'missing_collection'
        ai = self.read('openai-status.json', {}) or {}
        job = self.read('analysis-job.json', {}) or {}
        if ai.get('status') == 'error':
            reason = ai.get('reason') or 'api_error'
        if job.get('status') == 'error':
            reason = reason or 'api_error'
        from monitoring import REASONS
        return {'state': 'stopped' if reason else 'watching',
                'reason': reason, 'collected_at': packet.get('collected_at'),
                'description': REASONS.get(reason, 'Duomenys surenkami ir analizuojami paspaudus mygtuką.')}

    def collect(self):
        from diaspora_client import DiasporaClient
        owner = uuid.uuid4().hex
        acquired = self.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
            VALUES($1,$2,now()+interval '6 minutes')
            ON CONFLICT(scope) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
            WHERE signalas_jobs.expires_at<now() RETURNING owner''', [self.scope, owner])['rows']
        if not acquired:
            return {'status': 'already_running'}
        try:
            client = DiasporaClient(self.config.get('DIASPORA_BASE_URL', 'https://diaspora.sauliai.lt'),
                                    self.config.get('DIASPORA_USERNAME'), self.config.get('DIASPORA_PASSWORD'))
            client.login()
            packet = client.collect()
            saved = sync(packet, self.connection, self.scope)
            self.write('collection-status.json', {'status': 'ok', 'checked_at': packet['collected_at']})
            self.packet = packet
            from cloud_analysis import enqueue
            analysis = enqueue(self)
            return {'status': 'ok', 'posts': packet['post_count'], 'comments': packet['comment_count'],
                    'collected_at': packet['collected_at'], 'cloud_storage': saved, 'analysis': analysis}
        except Exception:
            self.write('collection-status.json', {'status': 'error', 'checked_at': datetime.now(timezone.utc).isoformat()})
            raise ValueError('Duomenų surinkti nepavyko. Paskutinė sėkminga kopija duomenų bazėje išsaugota.') from None
        finally:
            self.sql('DELETE FROM signalas_jobs WHERE scope=$1 AND owner=$2', [self.scope, owner])


class CloudPath:
    def __init__(self, repository, name):
        self.repository, self.name = repository, name

    def __truediv__(self, name):
        return CloudPath(self.repository, self.name + '/' + name)

    def exists(self):
        return self.name in ('var/dashboard-mode.json', 'var/diaspora-latest.json') or self.repository.read(self.name.removeprefix('var/')) is not None

    def read_text(self, **kwargs):
        if self.name == 'var/dashboard-mode.json':
            value = {'mode': 'live'}
        elif self.name == 'var/diaspora-latest.json':
            value = self.repository.latest()
        else:
            value = self.repository.read(self.name.removeprefix('var/'))
        return json.dumps(value)
