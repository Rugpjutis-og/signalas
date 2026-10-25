"""Neon-backed application state and read adapter; never writes local files."""
import json
import uuid
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

from cloud_storage import query, account_scope, sync, CloudStorageError, SCHEMA as FETCH_SCHEMA
from integration_config import ROOT
from thermometer_policy import VERSION

SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS signalas_state (
        scope text NOT NULL, name text NOT NULL, value jsonb NOT NULL,
        PRIMARY KEY(scope,name))''',
    '''CREATE TABLE IF NOT EXISTS signalas_jobs (
        scope text PRIMARY KEY, owner text NOT NULL, expires_at timestamptz NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS signalas_login_attempts (
        identity text PRIMARY KEY, attempts integer NOT NULL, expires_at timestamptz NOT NULL)''',
]

# Schema readiness is only a short-lived process cache; application data stays in Neon.
_schema_ready = {}

# Read legacy aggregate assessments and new independent rows in chronological
# storage order. New results never rewrite the legacy multi-megabyte JSON array.
ASSESSMENTS = '''WITH assessments AS (
    SELECT a,0 AS stage,n FROM signalas_state,
      LATERAL jsonb_array_elements(value) WITH ORDINALITY t(a,n)
      WHERE scope=$1 AND name='openai-analysis-pilot.json'
    UNION ALL SELECT value AS a,1 AS stage,0 AS n FROM signalas_state
      WHERE scope=$1 AND name LIKE 'analysis-result/%') '''
ASSESSMENT_ORDER = "stage,n,COALESCE(a->>'recorded_at',a->>'classified_at',a->>'analyzed_at','')"


def analysis_result_name(result):
    binding = {k: result.get(k) for k in ('content_fingerprint', 'exercise_id', 'exercise_context',
                'registry_version', 'thermometer_rules_version')}
    binding['source'] = result.get('source_reference', {}).get('source')
    binding['id'] = result.get('source_reference', {}).get('id')
    binding['model'] = result.get('requested_model', result.get('model'))
    if result.get('vision_revision'):
        binding['vision_revision'] = result['vision_revision']
    if result.get('exercise_actor_context_revision'):
        binding['exercise_actor_context_revision']=result['exercise_actor_context_revision']
    if result.get('exercise_scoring_rule_review'):
        binding['exercise_scoring_rule_review'] = result['exercise_scoring_rule_review']
    if result.get('review_run_id'):
        binding['review_run_id'] = result['review_run_id']
    name = 'analysis-result/' + hashlib.sha256(json.dumps(binding, sort_keys=True,
                                                         ensure_ascii=False).encode()).hexdigest()
    return name


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
        identity = hashlib.sha256((self.connection or '').encode()).hexdigest()
        if time.monotonic() < _schema_ready.get(identity, 0):
            return
        query(self.connection, [{'query': sql, 'params': []} for sql in FETCH_SCHEMA + SCHEMA])
        _schema_ready[identity] = time.monotonic() + 300

    def read(self, name, default=None):
        if name not in self.values:
            if name == 'openai-analysis-pilot.json':
                rows = self.sql(ASSESSMENTS + 'SELECT COALESCE(jsonb_agg(a ORDER BY ' +
                                ASSESSMENT_ORDER + "),'[]'::jsonb) FROM assessments", [self.scope])['rows']
            else:
                rows = self.sql('SELECT value FROM signalas_state WHERE scope=$1 AND name=$2', [self.scope, name])['rows']
            self.values[name] = json.loads(rows[0][0]) if rows else default
        return self.values[name]

    def dashboard_analyses(self, identities, context):
        """Resolve small latest-result pointers, then fetch indexed bounded bodies.

        Source/history rows remain unchanged. Context is shared in memory rather
        than transferred once per result. Legacy array ordinals remain supported.
        """
        context_json = json.dumps(context,ensure_ascii=False)
        for offset in range(0,len(identities),1000):
            wanted = identities[offset:offset+1000]
            rows = self.sql("""WITH assessments AS (
                SELECT a,0 AS stage,n,'openai-analysis-pilot.json'::text AS row_name
                FROM signalas_state,LATERAL jsonb_array_elements(value) WITH ORDINALITY t(a,n)
                WHERE scope=$1 AND name='openai-analysis-pilot.json'
                UNION ALL SELECT value AS a,1 AS stage,0 AS n,name AS row_name
                FROM signalas_state WHERE scope=$1 AND name LIKE 'analysis-result/%'
            ), selected AS (
                SELECT DISTINCT ON(a->'source_reference'->>'source',a->'source_reference'->>'id')
                    row_name,n,a->'source_reference'->>'source' AS source,
                    a->'source_reference'->>'id' AS id,a->>'content_fingerprint' AS fingerprint
                FROM assessments JOIN jsonb_to_recordset($3::jsonb)
                    AS wanted(source text,id text,fingerprint text)
                  ON a->'source_reference'->>'source'=wanted.source
                    AND a->'source_reference'->>'id'=wanted.id
                    AND a->>'content_fingerprint'=wanted.fingerprint
                WHERE (a->>'analysis_executed'='true' OR a->>'processing_disposition'='needs_review')
                  AND COALESCE(a->'exercise_context','null'::jsonb)=$2::jsonb
                ORDER BY a->'source_reference'->>'source',a->'source_reference'->>'id',
                    stage DESC,n DESC,COALESCE(a->>'recorded_at',a->>'classified_at',a->>'analyzed_at','') DESC
            ) SELECT COALESCE(jsonb_agg(to_jsonb(selected)),'[]'::jsonb) FROM selected""",
                [self.scope,context_json,json.dumps(wanted,ensure_ascii=False)])['rows']
            pointers = json.loads(rows[0][0]) if rows else []
            for page_start in range(0,len(pointers),100):
                page = pointers[page_start:page_start+100]
                rows = self.sql("""WITH selected AS (
                    SELECT CASE WHEN wanted.n>0 THEN s.value->(wanted.n-1) ELSE s.value END AS a,
                           wanted.source,wanted.id,wanted.fingerprint
                    FROM jsonb_to_recordset($2::jsonb)
                        AS wanted(row_name text,n integer,source text,id text,fingerprint text)
                    JOIN signalas_state s ON s.scope=$1 AND s.name=wanted.row_name
                ) SELECT COALESCE(jsonb_agg(a-'exercise_context'),'[]'::jsonb) FROM selected
                  WHERE a->'source_reference'->>'source'=source AND a->'source_reference'->>'id'=id
                    AND a->>'content_fingerprint'=fingerprint
                    AND COALESCE(a->'exercise_context','null'::jsonb)=$3::jsonb""",
                    [self.scope,json.dumps(page,ensure_ascii=False),context_json])['rows']
                results = json.loads(rows[0][0]) if rows else []
                if len(results) != len(page):
                    raise CloudStorageError('Dalis aktualių vertinimų nepasiekiama. Išsaugoti duomenys nepakeisti.')
                for analysis in results:
                    analysis['exercise_context'] = context
                    yield analysis


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
            rows = self.sql('''WITH latest AS (SELECT packet FROM signalas_fetches
                WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1)
                SELECT CASE WHEN packet->>'storage_version'='2' THEN packet || jsonb_build_object('records',
                    COALESCE((SELECT jsonb_agg(c.payload ORDER BY ref.n)
                      FROM jsonb_array_elements(packet->'record_keys') WITH ORDINALITY ref(k,n)
                      JOIN signalas_content c ON c.scope=$1 AND c.source=ref.k->>'source'
                        AND c.content_id=ref.k->>'id'),'[]'::jsonb)) ELSE packet END FROM latest''', [self.scope])['rows']
            self.packet = json.loads(rows[0][0]) if rows else {
                'records': [], 'source': 'diaspora.sauliai.lt', 'collected_at': None,
                'coverage': 'account_stream_and_own_profile', 'stream_complete': False}
            if self.packet.get('storage_version') == 2 and len(self.packet['records']) != len(self.packet['record_keys']):
                self.packet = None
                raise CloudStorageError('Trūksta surinkimo sąraše nurodytų įrašų. Ankstesni duomenys nepakeisti.')
        return self.packet

    def expand_unit(self, unit):
        if 'conversation_context' in unit or 'parent_post' in unit or getattr(self,'_bounded_analysis_units',{}).get((unit.get('source'),unit.get('id'))) is unit:
            return unit
        from discussion_context import DiscussionIndex
        records = self.latest()['records']
        if getattr(self, '_discussion_records', None) is not records:
            self._discussion_records = records
            self._discussion_index = DiscussionIndex(records)
        return self._discussion_index.expand(unit)

    def content_unit(self, source, identity):
        # A thumbnail must not download an entire multi-megabyte snapshot.
        rows = self.sql('''WITH latest AS (SELECT packet FROM signalas_fetches
            WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1)
            SELECT c.payload FROM latest,signalas_content c
            WHERE packet->>'storage_version'='2' AND c.scope=$1 AND c.source=$2 AND c.content_id=$3
              AND EXISTS (SELECT 1 FROM jsonb_array_elements(packet->'record_keys') ref
                          WHERE ref->>'source'=$2 AND ref->>'id'=$3)
            UNION ALL SELECT r FROM latest,LATERAL jsonb_array_elements(packet->'records') r
            WHERE COALESCE(packet->>'storage_version','1')<>'2' AND r->>'source'=$2 AND r->>'id'=$3''',
            [self.scope, source, identity])['rows']
        return json.loads(rows[0][0]) if rows else None

    def collected_at(self):
        from thermometer import instant
        if self.packet is not None:
            value = self.packet.get('collected_at')
            return instant(value).isoformat() if value else None
        rows = self.sql("SELECT packet->>'collected_at' FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1", [self.scope])['rows']
        return instant(rows[0][0]).isoformat() if rows else None

    def refresh_snapshot(self):
        # A batch reuses its snapshot while still detecting concurrent collections.
        if self.packet is not None:
            rows = self.sql("SELECT packet->>'collected_at' FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1", [self.scope])['rows']
            from thermometer import instant
            if not rows or instant(rows[0][0]) != instant(self.packet['collected_at']):
                self.packet = None

    def analysis_units(self, identities):
        from discussion_context import DiscussionIndex
        wanted={tuple(k) for k in identities}
        if self.packet is not None:
            index=DiscussionIndex(self.packet['records'])
            result={k:index.expand(index.units[k]) for k in wanted if k in index.units}
        else:
            rows=self.sql("""WITH latest AS(SELECT packet FROM signalas_fetches
                WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1),
                inventory AS(SELECT ref.k,ref.n FROM latest,
                  jsonb_array_elements(COALESCE(packet->'record_keys','[]'::jsonb)) WITH ORDINALITY ref(k,n)),
                requested AS(SELECT c.source,c.content_id,c.payload FROM signalas_content c
                  JOIN inventory i ON i.k->>'source'=c.source AND i.k->>'id'=c.content_id
                  WHERE c.scope=$1 AND EXISTS(SELECT 1 FROM jsonb_array_elements($2::jsonb) ref
                    WHERE ref->>0=c.source AND ref->>1=c.content_id)),
                needed AS(SELECT ref->>0 AS source,ref->>1 AS content_id FROM jsonb_array_elements($2::jsonb) ref
                  UNION SELECT source,payload->>'parent_id' FROM requested WHERE payload->>'kind'='comment'
                  UNION SELECT c.source,c.content_id FROM signalas_content c JOIN requested r
                    ON c.source=r.source AND c.payload->>'parent_id'=r.payload->>'parent_id'
                    AND r.payload->>'kind'='comment' AND c.payload->>'kind'='comment'
                    AND (c.payload->>'published_at')::timestamptz<=(r.payload->>'published_at')::timestamptz
                    WHERE c.scope=$1)
                SELECT COALESCE(jsonb_agg(c.payload ORDER BY i.n),'[]'::jsonb),
                  (SELECT count(*) FROM needed n2 JOIN inventory i2 ON i2.k->>'source'=n2.source AND i2.k->>'id'=n2.content_id)
                FROM needed n JOIN inventory i ON i.k->>'source'=n.source AND i.k->>'id'=n.content_id
                JOIN signalas_content c ON c.scope=$1 AND c.source=n.source AND c.content_id=n.content_id""",
                [self.scope,json.dumps(list(wanted))])['rows']
            records=json.loads(rows[0][0]) if rows else []
            if rows and len(records)!=int(rows[0][1]):
                raise CloudStorageError('Trūksta surinkimo sąraše nurodytų įrašų. Ankstesni duomenys nepakeisti.')
            index=DiscussionIndex(records)
            result={k:index.expand(index.units[k]) for k in wanted if k in index.units}
            # Legacy snapshots predate canonical records; keep their existing safe reader.
            if not result and wanted:
                metadata=self.sql("SELECT packet->>'storage_version' FROM signalas_fetches WHERE scope=$1 ORDER BY collected_at DESC LIMIT 1",[self.scope])['rows']
                if metadata and metadata[0][0]!='2':
                    index=DiscussionIndex(self.latest()['records'])
                    result={k:index.expand(index.units[k]) for k in wanted if k in index.units}
        self._bounded_analysis_units=getattr(self,'_bounded_analysis_units',{})
        self._bounded_analysis_units.update(result)
        return result

    def analysis_queue_page(self, generation, offset, limit):
        rows = self.sql("""SELECT COALESCE((SELECT jsonb_agg(t.v ORDER BY t.n)
            FROM jsonb_array_elements(value->'units') WITH ORDINALITY t(v,n)
            WHERE t.n>$3 AND t.n<=$3+$4),'[]'::jsonb)
            FROM signalas_state WHERE scope=$1 AND name='analysis-queue.json'
              AND value->>'generation'=$2""", [self.scope,generation,offset,limit])['rows']
        return json.loads(rows[0][0]) if rows else None

    def analysis_queue_results(self, units, context, version, model):
        identities = json.dumps([[u['source'],u['id']] for u in units])
        rows = self.sql(ASSESSMENTS + """SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'source_reference',a->'source_reference','content_fingerprint',a->'content_fingerprint',
            'exercise_id',a->'exercise_id','vision_revision',a->'vision_revision',
            'thermometer_status',a->'result'->'thermometer_status','processing_reason',a->'processing_reason')
            ORDER BY """ + ASSESSMENT_ORDER + """),'[]'::jsonb) FROM assessments
            WHERE (a->>'analysis_executed'='true' OR a->>'processing_disposition'='needs_review')
              AND a->>'registry_version'=$2 AND a->>'thermometer_rules_version'=$3
              AND COALESCE(a->'exercise_context','null'::jsonb)=$4::jsonb
              AND (COALESCE(a->>'requested_model',a->>'model')=$5 OR
                   (a->>'review_run_id' IS NOT NULL AND a->>'analysis_executed'='true' AND a->'result'->>'thermometer_status'='classified'))
              AND EXISTS(SELECT 1 FROM jsonb_array_elements($6::jsonb) ref
                WHERE ref->>0=a->'source_reference'->>'source' AND ref->>1=a->'source_reference'->>'id')""",
            [self.scope,version,VERSION,json.dumps(context),model,identities])['rows']
        return json.loads(rows[0][0]) if rows else []

    def analysis_worker(self, index):
        workers = getattr(self, '_analysis_worker_pool', {})
        if index not in workers:
            workers[index] = Repository(self.config)
            self._analysis_worker_pool = workers
        worker = workers[index]
        worker.packet = self.packet  # Immutable snapshot; photos/cookies/caches remain per worker.
        worker.values = dict(self.values)
        return worker

    def analysis_for_queue(self, context, version, model, *, include_reviews=False):
        # Filter in Postgres and transfer only identities/fingerprints, not every
        # original text, discussion, evidence and historic result on every unit.
        rows = self.sql(ASSESSMENTS + '''SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'source_reference',jsonb_build_object('source',a->'source_reference'->'source',
                'id',a->'source_reference'->'id'),'content_fingerprint',a->'content_fingerprint',
            'exercise_id',a->'exercise_id','vision_revision',a->'vision_revision',
            'thermometer_status',a->'result'->'thermometer_status',
            'processing_reason',a->'processing_reason') ORDER BY ''' + ASSESSMENT_ORDER + '''), '[]'::jsonb)
            FROM assessments WHERE (a->>'analysis_executed'='true' OR a->>'processing_disposition'='needs_review')
            AND a->>'registry_version'=$2 AND a->>'thermometer_rules_version'=$3
            AND COALESCE(a->'exercise_context','null'::jsonb)=$4::jsonb
            AND (COALESCE(a->>'requested_model',a->>'model')=$5 OR
                ($6::boolean AND a->>'review_run_id' IS NOT NULL AND a->>'analysis_executed'='true' AND a->'result'->>'thermometer_status'='classified'))''',
            [self.scope, version, VERSION, json.dumps(context), model,include_reviews])['rows']
        return json.loads(rows[0][0]) if rows else []

    def analysis_for_unit(self, source, identity, content_fingerprint, context):
        rows = self.sql(ASSESSMENTS + """SELECT a FROM assessments
            WHERE a->'source_reference'->>'source'=$2 AND a->'source_reference'->>'id'=$3
              AND a->>'content_fingerprint'=$4
              AND COALESCE(a->'exercise_context','null'::jsonb)=$5::jsonb
            ORDER BY stage DESC,n DESC,COALESCE(a->>'recorded_at',a->>'classified_at',a->>'analyzed_at','') DESC
            LIMIT 1""", [self.scope, source, identity, content_fingerprint, json.dumps(context)])['rows']
        return json.loads(rows[0][0]) if rows else None

    def append_analysis(self, result):
        name = analysis_result_name(result)
        self.sql('''INSERT INTO signalas_state(scope,name,value)
            VALUES($1,$2,$3::jsonb) ON CONFLICT(scope,name) DO NOTHING''',
            [self.scope, name, json.dumps(result)])
        self.values.pop('openai-analysis-pilot.json', None)

    def supplement_eligible(self, unit, effective_at):
        # Return a boolean, never transfer historical content or assessment bodies.
        # Missing legacy timestamps conservatively count as earlier assessments.
        from thermometer_review import key
        rows = self.sql(ASSESSMENTS + '''SELECT NOT (EXISTS (
            SELECT 1 FROM assessments WHERE a->>'analysis_executed'='true'
              AND a->'source_reference'->>'source'=$2 AND a->'source_reference'->>'id'=$3
              AND COALESCE(a->'exercise_id','null'::jsonb)=$4::jsonb
              AND COALESCE(NULLIF(COALESCE(a->>'classified_at',a->>'analyzed_at',
                    a->>'recorded_at'),''),'-infinity')::timestamptz < $5::timestamptz
            ) OR EXISTS (
            SELECT 1 FROM signalas_state WHERE scope=$1 AND name='thermometer-reviews.json'
              AND value ? $6
              AND COALESCE(value->$6->'exercise_id','null'::jsonb)=$4::jsonb
              AND COALESCE(NULLIF(value->$6->>'reviewed_at',''),'-infinity')::timestamptz < $5::timestamptz
            ))''', [self.scope, unit['source'], unit['id'], json.dumps(unit.get('exercise_id')),
                     effective_at, key(unit['source'], unit['id'])])['rows']
        return bool(rows and rows[0][0] in (True, 'true', 't'))

    def pending_claims(self, exercise_id, version):
        rows = self.sql(ASSESSMENTS + '''SELECT COALESCE(jsonb_agg(DISTINCT jsonb_build_object(
            'title',p->'title','topic_id',p->'topic_id','claim_template',p->'claim_template',
            'novelty_reason',p->'novelty_reason')),'[]'::jsonb)
            FROM assessments,
            LATERAL jsonb_array_elements(COALESCE(a->'result'->'narrative_analysis'->'proposals','[]'::jsonb)) p
            WHERE a->>'registry_version'=$2 AND COALESCE(a->'exercise_id','null'::jsonb)=$3::jsonb''',
            [self.scope, version, json.dumps(exercise_id)])['rows']
        return json.loads(rows[0][0]) if rows else []

    def dashboard_revision(self):
        rows = self.sql('''SELECT md5(COALESCE(string_agg(name||md5(value::text),'' ORDER BY name),''))
            FROM signalas_state WHERE scope=$1 AND (name LIKE 'analysis-result/%' OR
                name IN ('openai-analysis-pilot.json','live-context.json','dashboard-period.json',
                         'thermometer-reviews.json','narrative-registry-state.json','narrative-subnarratives.json',
                         'analysis-context-supplement.json'))''', [self.scope])['rows']
        return hashlib.sha256(json.dumps([self.collected_at(), rows]).encode()).hexdigest()

    def __truediv__(self, name):
        return CloudPath(self, name) if name.startswith('var') else ROOT / name

    def monitoring_status(self, **kwargs):
        failure = self.read('collection-status.json', {}) or {}
        reason = 'collection_failed' if failure.get('status') == 'error' else None
        collected_at = kwargs.get('collected_at') or self.collected_at()
        if not collected_at:
            reason = reason or 'missing_collection'
        else:
            from monitoring import MAX_COLLECTION_AGE, _instant
            try:
                current = kwargs.get('now') or datetime.now(timezone.utc)
                if current - _instant(collected_at) > MAX_COLLECTION_AGE:
                    reason = reason or 'stale_collection'
            except (ValueError, TypeError, AttributeError):
                reason = reason or 'status_unavailable'
        ai = self.read('openai-status.json', {}) or {}
        job = self.read('analysis-job.json', {}) or {}
        if ai.get('status') == 'error':
            reason = ai.get('reason') or 'api_error'
        if job.get('status') == 'error':
            reason = reason or 'api_error'
        from monitoring import REASONS
        return {'state': 'stopped' if reason else 'watching',
                'reason': reason, 'collected_at': collected_at,
                'description': REASONS.get(reason, 'Duomenys renkami ir analizuojami Vercel fone.')}

    def collection_progress(self):
        rows=self.sql("""SELECT jsonb_build_object('kind','collection','status',value->'status',
            'phase',value->'phase','processed_posts',COALESCE(value->'detail_cursor','0'::jsonb),
            'discovered_posts',jsonb_array_length(COALESCE(value->'entries','[]'::jsonb)),
            'remaining',GREATEST(0,jsonb_array_length(COALESCE(value->'entries','[]'::jsonb))-
                COALESCE((value->>'detail_cursor')::int,0)))
            FROM signalas_state WHERE scope=$1 AND name='collection-job.json'""",[self.scope])['rows']
        return json.loads(rows[0][0]) if rows else {'kind':'collection','status':'idle'}

    def collect(self, *, reset_analysis_error=True):
        from diaspora_client import DiasporaClient, DiasporaRequestError
        owner = uuid.uuid4().hex
        acquired = self.sql('''INSERT INTO signalas_jobs(scope,owner,expires_at)
            VALUES($1,$2,now()+interval '6 minutes')
            ON CONFLICT(scope) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at
            WHERE signalas_jobs.expires_at<now() RETURNING owner''', [self.scope, owner])['rows']
        if not acquired:
            return {'status': 'already_running'}
        stage = 'login'
        try:
            client = DiasporaClient(self.config.get('DIASPORA_BASE_URL', 'https://diaspora.sauliai.lt'),
                                    self.config.get('DIASPORA_USERNAME'), self.config.get('DIASPORA_PASSWORD'))
            from cloud_collection import run_step
            stage = 'source'
            outcome = run_step(self, client)
            if outcome['status'] == 'pending':
                self.write('collection-status.json', dict(outcome, status='running',
                    checked_at=datetime.now(timezone.utc).isoformat()))
                return outcome
            self.write('collection-status.json', {'status': 'ok', 'checked_at': outcome['collected_at']})
            from cloud_analysis import enqueue
            stage = 'enqueue'
            outcome['analysis'] = enqueue(self, reset_error=reset_analysis_error)
            return outcome
        except Exception as error:
            progress = self.values.get('collection-job.json') or {}
            if progress.get('status') == 'running':
                self.write('collection-job.json', dict(progress, status='error'))
            reason = error.reason if isinstance(error, (DiasporaRequestError, CloudStorageError)) else 'collection_validation'
            self.write('collection-status.json', {'status': 'error', 'stage': stage, 'reason': reason,
                'http_status': error.http_status if isinstance(error, DiasporaRequestError) else None,
                'resource': error.resource if isinstance(error, DiasporaRequestError) else None,
                'error_type': type(error).__name__ if type(error).__name__ in
                    ('ValueError','KeyError','TypeError','CloudStorageError','DiasporaRequestError') else 'internal',
                'checked_at': datetime.now(timezone.utc).isoformat()})
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
