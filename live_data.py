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
import monitoring

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
    for unit in packet["records"]:
        records.setdefault((unit["source"], unit["id"]), unit)
    packet["records"] = list(records.values())
    context_path = root / "var/live-context.json"
    context = context_data(json.loads(context_path.read_text(encoding="utf-8"))) if context_path.exists() else None
    analysis_path = root / "var/openai-analysis-pilot.json"
    analyses = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else []
    assessed = {}
    for analysis in analyses:
        ref = analysis.get("source_reference", {})
        key = (ref.get("source"), ref.get("id"))
        unit = records.get(key)
        if (unit and analysis.get("analysis_executed") is True and analysis.get("exercise_context") == context
                and analysis.get("content_fingerprint") == fingerprint(unit)):
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
    from integrations import private_json
    if start_date is None:
        # Backwards-compatible end-only clients retain their saved duration.
        first, last = bounds({}, None, root) if (root / "var/dashboard-period.json").exists() else (None, None)
        duration = (last.date() - first.date()).days if first else MAX_PERIOD
        parsed = date.fromisoformat(end_date)
        start_date = (parsed - timedelta(days=duration - 1)).isoformat()
    calendar_range(start_date, end_date)  # Validate before changing the saved selection.
    private_json(root / "var/dashboard-period.json", {"start_date": start_date, "end_date": end_date})


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
    catalog = json.loads((root / "data/catalog.json").read_text(encoding="utf-8"))
    known = {n["id"]: n for n in catalog["narratives"]}
    narratives, units = {}, []
    days = [(start.date() + timedelta(days=i)).isoformat() for i in range(duration)]
    for record in records:
        analysis = analyses.get((record["source"], record["id"]))
        result = analysis["result"] if analysis else None
        unit = {**record, "analysis": result, "analysis_executed": bool(analysis),
                "stance": result["stance"] if result else "unknown"}
        units.append(unit)
        if not result or not (result.get("narrative_id") or result.get("candidate_title")):
            continue
        definition = known.get(result["narrative_id"])
        title = definition["title"] if definition else result["candidate_title"]
        theme = definition["theme"] if definition else result["theme_id"] or "unassigned"
        identity = definition["id"] if definition else "C-" + hashlib.sha256(
            (theme + ":" + " ".join(title.casefold().split())).encode()).hexdigest()[:10]
        unit["narrative_id"] = identity
        if identity not in narratives:
            narratives[identity] = {
                "id": identity, "title": title, "lines": [title[:27], title[27:54]] if len(title) > 27 else [title],
                "description": definition["description"] if definition else result["reason"],
                "theme": theme, "source": "user_list" if definition else "ai_proposal",
                "status": "confirmed" if definition else "candidate", "fixed": False, "is_live": True,
                "history_complete": False, "exercise_id": packet.get("exercise_id"), "days": [0] * duration,
                "dailyStances": [[0, 0, 0] for _ in range(duration)], "evidence": [],
                "firstSeenAt": record["published_at"], "first": "", "actors": [], "places": [], "secondaryThemes": []}
        narrative = narratives[identity]
        day = instant(record["published_at"]).astimezone(ZONE).date().isoformat()
        index = days.index(day)
        narrative["days"][index] += 1
        if unit["stance"] in ("support", "oppose", "quote"):
            narrative["dailyStances"][index][("support", "oppose", "quote").index(unit["stance"])] += 1
        narrative["evidence"].append(unit)
        if instant(record["published_at"]) < instant(narrative["firstSeenAt"]):
            narrative["firstSeenAt"] = record["published_at"]
    return {"mode": "live", "source": packet["source"], "collected_at": packet["collected_at"],
            "monitoring": monitoring.status(root, collected_at=packet["collected_at"]),
            "coverage": packet["coverage"], "collection_scope": coverage(packet,start,end),
            "stream_complete": packet.get("stream_complete",False), "exercise_id": packet.get("exercise_id"),
            "start": start.isoformat(), "end": end.isoformat(), "days": days, "period": duration,
            "range_saved": bool(json.loads((root / "var/dashboard-period.json").read_text()).get("start_date")),
            "context_available": context is not None,
            "units": units, "narratives": list(narratives.values()), "relations": [],
            "analysis_count": sum(u["analysis_executed"] for u in units)}


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
    start, end = bounds(packet, period, root, start_date=start_date, end_date=end_date)
    period = (end.date() - start.date()).days
    rows = []
    for record in scoped(packet["records"], start, end):
        analysis = analyses.get((record["source"], record["id"]))
        result = analysis["result"] if analysis else None
        direction = result["direction"] if result else "needs_review"
        assessed = direction in CATEGORIES
        assessment = {"category": direction if assessed else None, "status": "assessed" if assessed else "needs_review",
                      "method": "openai_text_pilot" if analysis else "not_analyzed",
                      "reason": (result["reason"] if assessed else result["missing_context"] or result["reason"]) if result else "AI analizė šiam turiniui dar neatlikta.",
                      "context_version": None, "reviewed_parts": ["text"] if analysis else [],
                      "evidence": [{"kind": "text", "quote": result["evidence"]}] if result and result["evidence"] else []}
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
            "analysis": "OpenAI teksto bandymas; medija neperžiūrėta.", "units": rows,
            "days": days, **proportions(rows)}
