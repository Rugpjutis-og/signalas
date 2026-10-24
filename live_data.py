"""Read-only projections of the collected account-visible sample and AI proposals."""
import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from content import source_reference
from integration_config import ROOT
from openai_analysis import context_data
from platform_overview import report as platform_report
from periods import PERIODS, MAX_PERIOD, calendar_range
from thermometer import CATEGORIES, LABELS, instant, proportions
from thermometer_policy import VERSION as THERMOMETER_RULES_VERSION
import monitoring
import narrative_registry
import narrative_projection
from discussion_context import DiscussionIndex, compact_records, COMMENT_PART

ZONE = ZoneInfo("Europe/Vilnius")


def enabled(root=ROOT):
    path = root / "var/dashboard-mode.json"
    return path.exists() and json.loads(path.read_text()).get("mode") == "live"


def fingerprint(unit):
    fields = {key: unit.get(key) for key in ("source", "id", "published_at", "text", "media",
                                            "parent_post", "conversation_context")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load(root=ROOT):
    path = root / "var/diaspora-latest.json"
    packet = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "records": [], "collected_at": datetime.now(ZONE).isoformat(), "source": "diaspora.sauliai.lt",
        "coverage": "account_visible_stream_first_page", "stream_complete": False}
    records = {}
    for unit in compact_records(packet["records"]):
        records.setdefault((unit["source"], unit["id"]), unit)
    packet["records"] = list(records.values())
    discussions = DiscussionIndex(packet['records'])
    context_path = root / "var/live-context.json"
    context = context_data(json.loads(context_path.read_text(encoding="utf-8"))) if context_path.exists() else None
    analysis_path = root / "var/openai-analysis-pilot.json"
    analyses = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else []
    assessed = {}
    for analysis in analyses:
        ref = analysis.get("source_reference", {})
        key = (ref.get("source"), ref.get("id"))
        unit = records.get(key)
        if (unit and (analysis.get("analysis_executed") is True or
                      analysis.get("processing_disposition") == "needs_review") and
                analysis.get("exercise_context") == context
                and analysis.get("content_fingerprint") == fingerprint(discussions.expand(unit))):
            assessed[key] = analysis
    return packet, context, assessed


def bounds(packet, period=None, root=ROOT, *, start_date=None, end_date=None):
    if start_date is not None or end_date is not None:
        return calendar_range(start_date, end_date)
    if period is not None and period not in PERIODS:
        raise ValueError("Laikotarpis turi būti 10, 7, 3 arba 1 diena")
    path = root / "var/dashboard-period.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if period is None and saved.get("start_date"):
            return calendar_range(saved["start_date"], saved["end_date"])
        chosen = date.fromisoformat(saved["end_date"])
    else:
        # Freeze the initially displayed range; never anchor it to available content.
        chosen = datetime.now(ZONE).date()
        store_period(chosen.isoformat(), root)
    end = datetime.combine(chosen + timedelta(days=1), time(), ZONE)
    start = datetime.combine(chosen - timedelta(days=(period or MAX_PERIOD) - 1), time(), ZONE)
    return start, end


def store_period(end_date, root=ROOT, *, start_date=None):
    if start_date is None:
        # Backwards-compatible end-only clients retain their saved duration.
        first, last = bounds({}, None, root) if (root / "var/dashboard-period.json").exists() else (None, None)
        duration = (last.date() - first.date()).days if first else MAX_PERIOD
        parsed = date.fromisoformat(end_date)
        start_date = (parsed - timedelta(days=duration - 1)).isoformat()
    calendar_range(start_date, end_date)  # Validate before changing the saved selection.
    value = {"start_date": start_date, "end_date": end_date}
    if hasattr(root, 'write'):
        root.write('dashboard-period.json', value)
    else:
        from integrations import private_json
        private_json(root / "var/dashboard-period.json", value)


def coverage(packet, start, end):
    scope = packet.get("scope") or {}
    full = packet.get("coverage") == "administrator_pod_export" and packet.get("stream_complete") is True
    covered = full and instant(scope["from"]) <= start and end <= instant(scope["until"])
    return {"kind": packet.get("coverage"), "full_platform_export": bool(full),
            "selected_period_complete": bool(covered), "scope": scope,
            "account_scope": packet.get("account_scope")}


def scoped(records, start, end):
    return [r for r in records if start <= instant(r["published_at"]) < end]


def store_context(value, root=ROOT):
    if hasattr(root, 'save_context'):
        return root.save_context(value)
    from integrations import private_json
    value = context_data(value)
    path = root / "var/live-context.json"
    if value is None:
        path.unlink(missing_ok=True)
    else:
        private_json(path, value)


def bootstrap(root=ROOT):
    if not enabled(root):
        return {"mode": "demo"}
    packet, context, analyses = load(root)
    start, end = bounds(packet, None, root)
    duration = (end.date() - start.date()).days
    records = scoped(packet["records"], start, end)
    registry = narrative_registry.load(root)
    days = [(start.date() + timedelta(days=i)).isoformat() for i in range(duration)]
    projection = narrative_projection.project(records, analyses, registry, days, ZONE, context, packet.get("exercise_id"))
    import subnarratives
    branches = subnarratives.compact(subnarratives.project(records, analyses, registry))
    projection['narratives'] = subnarratives.attach(projection['narratives'],branches,registry,days,packet.get('exercise_id'))
    first_seen = {}
    for record in packet["records"]:
        current = narrative_projection.valid_analysis(record, analyses.get(narrative_projection.key(record)), registry)
        for match in current["matches"] if current else []:
            old = first_seen.get(match["type_id"])
            if old is None or instant(record["published_at"]) < instant(old):
                first_seen[match["type_id"]] = record["published_at"]
    for narrative in projection["narratives"]:
        narrative["firstSeenAt"] = first_seen[narrative["id"]]
    proposed = narrative_projection.candidates(packet, analyses, registry,
        decisions={**narrative_registry.state(root).get("decisions", {}), **{b['id']:b for b in registry.get('subnarratives',[])}})
    # The queue covers the last 24 h; do not display candidates outside the chosen interval.
    proposed = [c for c in proposed if any(start <= instant(u["published_at"]) < end for u in c["evidence"])]
    revision = narrative_registry.digest([registry["version"], list(analyses.values()), proposed, registry.get("subnarratives",[])])
    return {"mode": "live", "source": packet["source"], "collected_at": packet["collected_at"],
            "monitoring": monitoring.status(root, collected_at=packet["collected_at"]),
            "coverage": packet["coverage"], "collection_scope": coverage(packet,start,end),
            "stream_complete": packet.get("stream_complete",False), "exercise_id": packet.get("exercise_id"),
            "start": start.isoformat(), "end": end.isoformat(), "days": days, "period": duration,
            "range_saved": bool(json.loads((root / "var/dashboard-period.json").read_text()).get("start_date")),
            "context_available": context is not None,
            **projection, "registry": narrative_registry.public_registry(registry),
            "subnarratives": branches, "candidates": proposed, "candidate_policy": narrative_registry.CANDIDATE_POLICY,
            "analysis_revision": revision,
            "analysis_count": sum(u["analysis_executed"] for u in projection["units"])}


def platform(period=None, root=ROOT, *, start_date=None, end_date=None):
    packet, _, _ = load(root)
    start, end = bounds(packet, period, root, start_date=start_date, end_date=end_date)
    period = (end.date() - start.date()).days
    result = platform_report(packet["records"], packet.get("membership_snapshots",[]),
                             exercise_id=packet.get("exercise_id"), start=start, end=end, mode="live")
    result.update(period=period, coverage=packet["coverage"], collection_scope=coverage(packet,start,end),
                  stream_complete=packet.get("stream_complete",False),
                  collected_post_count=sum(r["kind"] in ("post", "reshare") for r in packet["records"]),
                  collected_at=packet["collected_at"], posts=[r for r in scoped(packet["records"], start, end)
                                                            if r["kind"] in ("post", "reshare")])
    # UI receives original content, not interaction/member identity lists.
    from platform_overview import public_content
    result["posts"] = [public_content(p) for p in result["posts"]]
    return result


def thermometer(period=None, root=ROOT, *, start_date=None, end_date=None):
    packet, context, analyses = load(root)
    discussions = DiscussionIndex(packet['records'])
    from thermometer_review import applicable, key as review_key, saved as saved_reviews
    manual_reviews = saved_reviews(root)
    start, end = bounds(packet, period, root, start_date=start_date, end_date=end_date)
    period = (end.date() - start.date()).days
    rows = []
    for record in scoped(packet["records"], start, end):
        analysis = analyses.get((record["source"], record["id"]))
        result = analysis["result"] if analysis else None
        current_rules = bool(analysis and analysis.get("thermometer_rules_version") == THERMOMETER_RULES_VERSION)
        status = result.get("thermometer_status") if current_rules else "not_analyzed" if not result else "needs_review"
        direction = result.get("thermometer_category") if current_rules else None
        assessed = status == "classified" and direction in CATEGORIES
        assessment = {"category": direction if assessed else None, "status": "assessed" if assessed else status,
                      "method": analysis.get("method", "not_analyzed") if analysis else "not_analyzed",
                      "reason": ((result.get("reason") if assessed else result.get("missing_context") or result.get("reason"))
                                 if current_rules else "Vertinimas atliktas pagal ankstesnes taisykles; reikia pakartotinės peržiūros.") if result else "AI analizė šiam turiniui dar neatlikta.",
                      "context_version": None, "reviewed_parts": (["text"] + (["images"] if analysis.get("image_review", {}).get("reviewed_image_refs") else [])) if analysis and analysis.get("analysis_executed") else [],
                      "reason_codes": result.get("reason_codes", []) if current_rules else [],
                      "rules_version": analysis.get("thermometer_rules_version") if analysis else None,
                      "evidence": [{"kind": "image" if result["evidence"].startswith("VAIZDAS[") else "text", "quote": result["evidence"]}] if current_rules and result.get("evidence") else []}
        manual = manual_reviews.get(review_key(record['source'], record['id']))
        if applicable(manual, discussions.expand(record), context):
            assessment = {"category": manual['category'], "status": "assessed", "method": "manual_review",
                          "reason": manual['reason'], "context_version": None,
                          "reviewed_parts": ["analitiko peržiūra"],
                          "reason_codes": [manual['reason_code']] if manual.get('reason_code') else [], "rules_version": manual['rules_version'],
                          "evidence": [{"kind": "text", "quote": manual['evidence']}] if manual['evidence'] else []}
        rows.append({**record, "attachments": [], "conversation_context": record.get("conversation_context", []),
                     "assessment": assessment})
    rows.sort(key=lambda r: instant(r["published_at"]), reverse=True)
    days = []
    day = start.date()
    while day < end.date():
        selected = [u for u in rows if instant(u["published_at"]).astimezone(ZONE).date() == day]
        days.append({"date": day.isoformat(), **proportions(selected)})
        day += timedelta(days=1)
    return {"mode": "live", "period": period, "start": start.isoformat(), "end": end.isoformat(),
            "coverage": packet["coverage"], "collection_scope": coverage(packet,start,end),
            "contexts": [], "exercise_context": context,
            "context_records": [{k: r.get(k) for k in ('source', 'kind', 'parent_id') + COMMENT_PART}
                                for r in packet['records']],
            "analysis": "OpenAI teksto ir prieinamų nuotraukų analizė; garsas ir vaizdo klipai neanalizuojami.", "rules_version": THERMOMETER_RULES_VERSION,
            "units": rows,
            "days": days, **proportions(rows)}
