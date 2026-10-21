"""Read-only collection and explicit AI pilots; collection never triggers paid AI."""
import argparse
import fcntl
import json
import os
import tempfile
from pathlib import Path

from app import DEFAULT_DB, import_file, normalize
from diaspora_client import DiasporaClient
from integration_config import ROOT, settings
from openai_analysis import analyze
from openai_check import check
import monitoring
import cloud_storage


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect_sample(db_path=DEFAULT_DB):
    # Prevent overlap between a manual refresh and the hourly task.
    (ROOT / "var").mkdir(exist_ok=True)
    fd = os.open(ROOT / "var/collection.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running"}
        try:
            config = settings()
            client = DiasporaClient(config.get("DIASPORA_BASE_URL", "https://diaspora.sauliai.lt"),
                                    config.get("DIASPORA_USERNAME"), config.get("DIASPORA_PASSWORD"))
            client.login()
            packet = client.collect()
            result = save_packet(packet, db_path)
            if config.get("SIGNALAS_DATABASE_URL"):
                try:
                    result["cloud_storage"] = cloud_storage.sync(packet, config["SIGNALAS_DATABASE_URL"], cloud_storage.account_scope(config))
                except cloud_storage.CloudStorageError as error:
                    result["cloud_storage"] = {"status": "error", "message": str(error)}
            return result
        except (ValueError, OSError):
            monitoring.record("collection", "collection_failed", ROOT)
            raise


def save_packet(packet, db_path=DEFAULT_DB):
    rows, skipped = [], 0
    for record in packet["records"]:
        row = {**record, "external_id": record["id"], "narrative_id": None, "stance": "unknown"}
        try:
            normalize(row, len(rows) + 1)
        except ValueError:
            skipped += 1
            continue
        rows.append(row)
    packet["importable_count"] = len(rows)
    packet["skipped_import_count"] = skipped
    if skipped:
        packet["stream_complete"] = False
        packet.setdefault("warnings", []).append("Dalis turinio neimportuota; pilnumas nepatvirtinamas.")
    path = ROOT / "var/diaspora-import.json"
    private_json(path, rows)
    imported = import_file(path, db_path)
    # Publish only after a successful import, atomically for concurrent readers.
    private_json(ROOT / "var/diaspora-latest.json", packet)
    monitoring.record("collection", root=ROOT)
    return {"status": "ok", "posts": packet["post_count"], "comments": packet["comment_count"],
            "media": sum(len(r.get("media") or []) for r in packet["records"]),
            "with_original_link": sum(bool(r.get("sourceUrl") or r.get("parentSourceUrl")) for r in packet["records"]),
            "coverage": packet["coverage"], "stream_complete": packet.get("stream_complete", False),
            "account_scope": packet.get("account_scope"),
            "exercise_id": packet.get("exercise_id"), "imported": imported, "skipped_import_count": skipped}


def ai_test():
    unit = {"id": "ai-connection-test", "source": "local-synthetic-test", "kind": "post",
            "published_at": "2026-10-21T09:00:00Z", "text": "Šiandien kepiau obuolių pyragą.",
            "media": [], "is_demo": True}
    context = {"initialSituation": "Fiktyvios pratybos. Įprastas gyvenimas išgalvotame mieste.",
               "confirmedFacts": "Jokių incidentų šiame bandyme nepaskelbta.", "nameMappings": []}
    result = analyze(unit, context)
    private_json(ROOT / "var/openai-test.json", result)
    return {"status": "ok", "model": result["model"], "structured_result": True,
            "direction": result["result"]["direction"], "synthetic_input": True,
            "usage": result["usage"], "dashboard": "demo"}


def main():
    parser = argparse.ArgumentParser(description="Signalas · Diaspora ir OpenAI bandomosios jungtys")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-openai")
    sub.add_parser("ai-test")
    fetch = sub.add_parser("collect-sample", help="Visi paskyros srauto ir savo profilio puslapiai; ne visa platforma")
    fetch.add_argument("--db", type=Path, default=DEFAULT_DB)
    full = sub.add_parser("collect", help="Visos platformos administratoriaus eksporto importas")
    full.add_argument("--export", dest="export_file", type=Path, required=True)
    full.add_argument("--db", type=Path, default=DEFAULT_DB)
    pilot = sub.add_parser("analyze")
    pilot.add_argument("--limit", type=int, default=1)
    pilot.add_argument("--context", type=Path)
    args = parser.parse_args()
    if args.command == "check-openai":
        print(check())
    elif args.command == "ai-test":
        print(json.dumps(ai_test(), ensure_ascii=False))
    elif args.command == "collect-sample":
        print(json.dumps(collect_sample(args.db), ensure_ascii=False))
    elif args.command == "collect":
        from admin_export import read_export
        print(json.dumps(save_packet(read_export(args.export_file), args.db), ensure_ascii=False))
    else:
        if not 1 <= args.limit <= 5:
            raise ValueError("AI bandymo limitas turi būti 1–5 turinio vienetai.")
        packet = json.loads((ROOT / "var/diaspora-latest.json").read_text(encoding="utf-8"))
        context = json.loads(args.context.read_text(encoding="utf-8")) if args.context else None
        from live_data import fingerprint
        target = ROOT / "var/openai-analysis-pilot.json"
        previous = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
        by_key = {(r["source"], r["id"]): r for r in packet["records"]}
        results = [r for r in previous if
                   (r.get("source_reference", {}).get("source"), r.get("source_reference", {}).get("id")) in by_key
                   and r.get("exercise_context") == context
                   and r.get("content_fingerprint") == fingerprint(by_key[(r["source_reference"]["source"], r["source_reference"]["id"])])]
        errors = []
        for unit in packet["records"][:args.limit]:
            if any(r["source_reference"]["source"] == unit["source"] and r["source_reference"]["id"] == unit["id"] for r in results):
                continue
            try:
                result = analyze(unit, context)
            except ValueError as error:
                errors.append({"source": unit["source"], "id": unit["id"], "reason": str(error)})
                continue
            result["content_fingerprint"] = fingerprint(unit)
            results.append(result)
            private_json(target, results)
        private_json(ROOT / "var/openai-analysis-errors.json", errors)
        print(json.dumps({"status": "partial" if errors else "ok", "analyzed": len(results),
                          "failed": len(errors), "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        # Do not include raw HTTP responses or tracebacks containing request objects.
        print("Bandymas nepavyko: %s" % error)
        raise SystemExit(1)
