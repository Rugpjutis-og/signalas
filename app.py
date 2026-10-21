"""Local Signalas server and offline ingestion. Python 3.9+, standard library only."""
import argparse
import csv
import json
import sqlite3
import sys
import secrets

from thermometer import demo_report
from metrics import metrics_context
from content import normalize_media, source_reference
from platform_overview import demo_report as platform_demo_report
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "var" / "signalas.sqlite3"
LIVE_CSRF = secrets.token_urlsafe(32)
STANCES = {"support", "oppose", "quote", "unknown"}


def catalog():
    return json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS posts (
        source TEXT NOT NULL, external_id TEXT NOT NULL,
        published_at TEXT NOT NULL, text TEXT NOT NULL,
        narrative_id TEXT, stance TEXT NOT NULL,
        is_demo INTEGER NOT NULL, imported_at TEXT NOT NULL,
        PRIMARY KEY (source, external_id))""")
    columns = {row[1] for row in db.execute('PRAGMA table_info(posts)')}
    for name, definition in [('sourceUrl', 'TEXT'), ('parentSourceUrl', 'TEXT'), ('kind', "TEXT NOT NULL DEFAULT 'post'"), ('media', "TEXT NOT NULL DEFAULT '[]'")]:
        if name not in columns:
            db.execute('ALTER TABLE posts ADD COLUMN %s %s' % (name, definition))
    db.commit()
    return db


def normalize(row, number):
    def fail(message):
        raise ValueError("Įrašas %s: %s" % (number, message))

    if not isinstance(row, dict):
        fail("tikimasi objekto")
    result = {}
    for field in ("source", "external_id", "published_at", "text"):
        value = row.get(field)
        if not isinstance(value, str) or (field != "text" and not value.strip()):
            fail("trūksta tekstinio lauko %s" % field)
        result[field] = value if field == 'text' else value.strip()
    try:
        date = datetime.fromisoformat(result["published_at"].replace("Z", "+00:00"))
        if date.tzinfo is None:
            fail("published_at turi turėti laiko juostą")
        result["published_at"] = date.astimezone(timezone.utc).isoformat()
    except ValueError as error:
        fail("netinkama published_at data (%s)" % error)
    narrative_id = row.get("narrative_id") or None
    known = {item["id"] for item in catalog()["narratives"]}
    if narrative_id is not None and (not isinstance(narrative_id, str) or narrative_id not in known):
        fail("nežinomas narrative_id; neaiškų priskyrimą palikite tuščią")
    result["narrative_id"] = narrative_id
    stance = row.get("stance") or "unknown"
    if not isinstance(stance, str) or stance not in STANCES:
        fail("stance turi būti support, oppose, quote arba unknown")
    result["stance"] = stance
    demo = row.get("is_demo")
    if isinstance(demo, str):
        demo = {"true": True, "false": False}.get(demo.lower())
    if not isinstance(demo, bool):
        fail("is_demo privalo būti true arba false")
    result["is_demo"] = int(demo)
    result["imported_at"] = datetime.now(timezone.utc).isoformat()
    try:
        reference = source_reference(row)
    except ValueError as error:
        fail(str(error))
    if reference['kind'] not in ('post', 'comment', 'reshare'):
        fail('kind turi būti post, comment arba reshare')
    result.update({key: reference[key] for key in ('sourceUrl', 'parentSourceUrl', 'kind')})
    try:
        media = row.get('media') or []
        if isinstance(media, str):
            media = json.loads(media)
        result['media'] = json.dumps(normalize_media(media, is_demo=bool(result['is_demo'])), ensure_ascii=False)
    except (ValueError, TypeError) as error:
        fail(str(error))
    if not result["text"].strip() and not json.loads(result["media"]) and result["kind"] != "reshare":
        fail("trūksta teksto arba paties įrašo medijos")
    return result


def import_file(path, db_path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".csv":
            rows = list(csv.DictReader(stream))
        elif path.suffix.lower() == ".json":
            rows = json.load(stream)
        else:
            raise ValueError("Naudokite .json arba .csv failą")
    if not isinstance(rows, list):
        raise ValueError("JSON viršutinis lygis turi būti įrašų masyvas")
    # Validate the entire batch before opening a transaction.
    records = [normalize(row, i) for i, row in enumerate(rows, 1)]
    db = connect(db_path)
    try:
        before = db.total_changes
        with db:
            db.executemany("""INSERT INTO posts (source, external_id, published_at, text, narrative_id,
                stance, is_demo, imported_at, sourceUrl, parentSourceUrl, kind, media) VALUES (
                :source, :external_id, :published_at, :text, :narrative_id,
                :stance, :is_demo, :imported_at, :sourceUrl, :parentSourceUrl, :kind, :media)
                ON CONFLICT(source, external_id) DO NOTHING""", records)
        added = db.total_changes - before
        return {"added": added, "duplicates": len(records) - added}
    finally:
        db.close()


def summary(db):
    return dict(db.execute("""SELECT COUNT(*) AS total,
        COALESCE(SUM(is_demo),0) AS demo,
        COALESCE(SUM(1-is_demo),0) AS non_demo,
        COALESCE(SUM(narrative_id IS NULL),0) AS unassigned FROM posts""").fetchone())


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, db_path, **kwargs):
        self.db_path = db_path
        super().__init__(*args, directory=str(ROOT / "dist"), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/media/image':
            import live_data
            if (not live_data.enabled() or self.headers.get('Host') != '127.0.0.1:%s' % self.server.server_port
                    or not secrets.compare_digest(self.headers.get('X-Signalas-CSRF', ''), LIVE_CSRF)):
                self.send_json({'error': 'Užklausa atmesta'}, 403)
                return
            try:
                from private_media import delivery
                query = parse_qs(url.query)
                body, mime = delivery.image(query['source'][0], query['id'][0], int(query['index'][0]))
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, KeyError, OSError):
                self.send_json({'error': 'Nuotraukos įkelti nepavyko'}, 502)
            return
        if url.path.startswith("/api/"):
            db = connect(self.db_path)
            try:
                if url.path == "/api/health":
                    import live_data
                    self.send_json({"status": "ok", "storage": "sqlite", "dashboard": "live" if live_data.enabled() else "demo"})
                elif url.path == "/api/dashboard/bootstrap":
                    import live_data
                    self.send_json(dict(live_data.bootstrap(), csrf=LIVE_CSRF))
                elif url.path == "/api/monitoring/status":
                    import monitoring
                    self.send_json(monitoring.status())
                elif url.path == "/api/thermometer":
                    try:
                        query = parse_qs(url.query, keep_blank_values=True)
                        period = int(query["period"][0]) if "period" in query else None
                        import live_data
                        report = live_data.thermometer(period, start_date=query.get("start_date", [None])[0],
                                                      end_date=query.get("end_date", [None])[0]) if live_data.enabled() else demo_report(period or 7)
                    except ValueError as error:
                        self.send_json({"error": str(error)}, 400)
                        return
                    self.send_json(report)
                elif url.path == "/api/metrics/context":
                    self.send_json(metrics_context())
                elif url.path == "/api/platform/overview":
                    try:
                        query = parse_qs(url.query, keep_blank_values=True)
                        period = int(query["period"][0]) if "period" in query else None
                        import live_data
                        self.send_json(live_data.platform(period, start_date=query.get("start_date", [None])[0],
                                                         end_date=query.get("end_date", [None])[0]) if live_data.enabled() else platform_demo_report(period or 7))
                    except ValueError as error:
                        self.send_json({'error': str(error)}, 400)
                elif url.path == "/api/catalog":
                    self.send_json(catalog())
                elif url.path == "/api/summary":
                    self.send_json(summary(db))
                elif url.path == "/api/posts":
                    query = parse_qs(url.query)
                    try:
                        limit = max(1, min(500, int(query.get("limit", [100])[0])))
                        offset = max(0, int(query.get("offset", [0])[0]))
                    except ValueError:
                        self.send_json({"error": "limit ir offset turi būti sveiki skaičiai"}, 400)
                        return
                    rows = db.execute("SELECT * FROM posts ORDER BY published_at DESC, source, external_id LIMIT ? OFFSET ?", (limit, offset))
                    posts = [dict(row) for row in rows]
                    for post in posts:
                        post['media'] = json.loads(post['media'])
                    self.send_json({"posts": posts, "limit": limit, "offset": offset})
                else:
                    self.send_json({"error": "Nerastas API kelias"}, 404)
            finally:
                db.close()
            return
        # Serve public UI files only, without directory listings or symlink traversal.
        target = Path(self.translate_path(url.path)).resolve()
        if not target.is_relative_to((ROOT / "dist").resolve()):
            self.send_error(404)
            return
        if target.is_dir() and not (target / "index.html").is_file():
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        import live_data
        if (self.path not in ("/api/dashboard/context", "/api/dashboard/period") or not live_data.enabled()
                or self.headers.get("Host") != "127.0.0.1:%s" % self.server.server_port
                or not secrets.compare_digest(self.headers.get("X-Signalas-CSRF", ""), LIVE_CSRF)):
            self.send_json({"error": "Užklausa atmesta"}, 403)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100000:
                raise ValueError("Netinkamas konteksto užklausos dydis")
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Reikia JSON objekto")
            if self.path == "/api/dashboard/period":
                live_data.store_period(payload["end_date"], start_date=payload.get("start_date"))
            else:
                if "context" not in payload:
                    raise ValueError("Reikia konteksto objekto")
                live_data.store_context(payload.get("context"))
            self.send_json(live_data.bootstrap())
        except (ValueError, UnicodeError, KeyError, TypeError) as error:
            self.send_json({"error": str(error)}, 400)


def main():
    parser = argparse.ArgumentParser(description="Signalas · vietinė Python versija")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Paleisti vietinę sąsają ir API")
    serve.add_argument("--port", type=int, default=8000)
    ingest = sub.add_parser("import", help="Importuoti vietinį JSON arba CSV")
    ingest.add_argument("file", type=Path)
    sub.add_parser("summary", help="Importuotų duomenų suvestinė")
    args = parser.parse_args()
    if args.command == "import":
        print(json.dumps(import_file(args.file, args.db), ensure_ascii=False))
    elif args.command == "summary":
        db = connect(args.db)
        try:
            print(json.dumps(summary(db), ensure_ascii=False))
        finally:
            db.close()
    else:
        connect(args.db).close()
        server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, db_path=args.db))
        print("Signalas: http://127.0.0.1:%s · sustabdyti: Ctrl+C" % server.server_port, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as error:
        print("Klaida: %s" % error, file=sys.stderr)
        sys.exit(1)
