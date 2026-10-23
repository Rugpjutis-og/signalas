"""Small persisted service health records; no credentials, content or remote checks."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from integration_config import ROOT

# Hourly collection plus 30 minutes of scheduling/network grace. Not a content filter.
MAX_COLLECTION_AGE = timedelta(minutes=90)
REASONS = {
    "collection_failed": "Nepavyko atnaujinti Diasporos duomenų.",
    "stale_collection": "Duomenys neatnaujinti ilgiau nei 90 minučių.",
    "missing_collection": "Dar nėra sėkmingai surinktų duomenų.",
    "api_quota": "AI API kreditai arba paskyros išlaidų / naudojimo limitas išnaudoti.",
    "api_connection": "Nutrūko ryšys su AI API.",
    "api_access": "AI API atmetė prieigą.",
    "api_rate_limit": "Pasiektas AI API užklausų dažnio limitas.",
    "api_error": "AI API užklausa nepavyko.",
    "status_unavailable": "Nepavyko patikrinti srauto būsenos.",
}


def record(service, reason=None, root=ROOT):
    """One record per service avoids collection/analysis overwriting each other."""
    if service not in ("collection", "openai") or reason is not None and reason not in REASONS:
        raise ValueError("Neatpažinta stebėjimo būsena")
    value = {"checked_at": datetime.now(timezone.utc).isoformat(),
             "status": "error" if reason else "ok", "reason": reason}
    if hasattr(root, 'write'):
        root.write(service + '-status.json', value)
    else:
        from integrations import private_json
        private_json(Path(root) / ("var/%s-status.json" % service), value)


def http_failure(error, root=ROOT):
    """Inspect only error codes. Never persist or expose raw provider messages."""
    try:
        if error.fp is None:
            raise ValueError("No response body")
        body = json.loads(error.read(65536))
        details = body.get("error", {}) if isinstance(body, dict) else {}
        code = details.get("code") if isinstance(details, dict) else None
        kind = details.get("type") if isinstance(details, dict) else None
    except (ValueError, OSError, TypeError, AttributeError):
        code = kind = None
    quota = {"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded",
             "project_spend_limit_exceeded", "organization_usage_limit_exceeded"}
    reason = ("api_quota" if isinstance(code, str) and code in quota or kind == "insufficient_quota" else
              "api_access" if error.code in (401, 403) else
              "api_rate_limit" if error.code == 429 else "api_error")
    record("openai", reason, root)
    return reason


def access_recovered(root=ROOT):
    """A successful models GET clears connection failures, never a billing block."""
    path = Path(root) / "var/openai-status.json"
    if path.exists():
        try:
            if json.loads(path.read_text()).get("reason") == "api_quota":
                return
        except (ValueError, OSError, AttributeError):
            return
    record("openai", root=root)


def _instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Reikia laiko juostos")
    return parsed


def status(root=ROOT, *, collected_at=None, now=None):
    if hasattr(root, 'monitoring_status'):
        return root.monitoring_status(collected_at=collected_at, now=now)
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    reason = None
    try:
        if collected_at is None:
            path = root / "var/diaspora-latest.json"
            collected_at = json.loads(path.read_text())["collected_at"] if path.exists() else None
        collected = _instant(collected_at) if collected_at else None
        for service in ("openai", "collection"):
            path = root / ("var/%s-status.json" % service)
            if not path.exists():
                continue
            result = json.loads(path.read_text())
            if result["status"] == "error":
                # A newer published snapshot proves collection recovery only.
                if service == "collection" and collected and collected > _instant(result["checked_at"]):
                    continue
                reason = result["reason"] if result.get("reason") in REASONS else "status_unavailable"
                break
        if not reason:
            reason = ("missing_collection" if not collected else
                      "stale_collection" if now - collected > MAX_COLLECTION_AGE or collected > now + timedelta(minutes=5) else None)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        reason = "status_unavailable"
    return {"state": "stopped" if reason else "watching",
            "label": "Srauto stebėjimas sustabdytas" if reason else "Stebimas srautas",
            "reason": reason, "description": REASONS.get(reason, "Duomenys atnaujinami kas valandą."),
            "collected_at": collected_at}
