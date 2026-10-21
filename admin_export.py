"""Import an administrator-supplied pod export, independent of any participant roster."""
import json
from urllib.parse import urlsplit

from platform_overview import adapt_diaspora_post, adapt_diaspora_comment
from thermometer import instant

FORMAT = "signalas.diaspora.export.v1"


def read_export(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("Neatpažintas administratoriaus eksporto formatas.")
    scope = data.get("scope")
    if not isinstance(scope, dict) or scope.get("kind") != "pod_database":
        raise ValueError("Eksporte turi būti aiškiai nurodyta visos platformos bazės aprėptis.")
    base = scope.get("source", "")
    url = urlsplit(base)
    if url.scheme != "https" or url.hostname != "diaspora.sauliai.lt" or url.username or url.password or url.path not in ("", "/"):
        raise ValueError("Eksporto šaltinis turi būti https://diaspora.sauliai.lt.")
    start, end = instant(scope["from"]), instant(scope["until"])
    if end <= start or not isinstance(data.get("raw_posts"), list):
        raise ValueError("Netinkamas eksporto laikotarpis arba įrašų sąrašas.")
    records, seen = [], {}
    def add(record):
        key = (record["source"], record["id"])
        if not isinstance(record["id"], str) or not record["id"]:
            raise ValueError("Eksporte trūksta pastovaus turinio GUID.")
        if key in seen:
            if seen[key] != record:
                raise ValueError("Eksporte dubliuojasi nesutampantis turinys.")
            return
        seen[key] = record
        records.append(record)
    for entry in data["raw_posts"]:
        raw = entry["post"]
        if raw.get("post_type") not in ("StatusMessage", "Reshare"):
            raise ValueError("Eksporte yra nepalaikomo tipo srauto turinys.")
        original = entry.get("sourceUrl")
        if original and urlsplit(original)[:2] != urlsplit(base)[:2]:
            raise ValueError("Įrašo originalo adresas nesutampa su eksporto platforma.")
        post = adapt_diaspora_post(raw, source=url.hostname, exercise_id=scope.get("exercise_id"),
                                  sourceUrl=original, interactions_complete=True, source_base_url=base)
        post["public"] = raw.get("public")
        if start <= instant(post["published_at"]) < end:
            add(post)
        comments = (raw.get("interactions") or {}).get("comments")
        if not isinstance(comments, list):
            raise ValueError("Eksporte nėra pilno komentarų sąrašo.")
        earlier = []
        for raw_comment in sorted(comments, key=lambda c: instant(c["created_at"])):
            comment = adapt_diaspora_comment(raw_comment, source=url.hostname, exercise_id=scope.get("exercise_id"),
                                            parentSourceUrl=original, source_base_url=base)
            comment["parent_id"] = post["id"]
            comment["parent_post"] = {key: post.get(key) for key in ("id", "text", "published_at", "media", "sourceUrl")}
            comment["conversation_context"] = list(earlier)
            if start <= instant(comment["published_at"]) < end:
                add(comment)
            earlier.append({key: comment.get(key) for key in ("id", "text", "published_at", "media", "sourceUrl", "parentSourceUrl")})
    posts = sum(r["kind"] in ("post", "reshare") for r in records)
    comments = sum(r["kind"] == "comment" for r in records)
    checks = [scope.get("complete") is True, scope.get("includes_private") is True,
              scope.get("contact_filter") is False, scope.get("membership_filter") is False,
              scope.get("database_read_only") is True, scope.get("expected_posts") == posts,
              scope.get("expected_comments") == comments]
    return {"mode": "live_export", "source": url.hostname, "collected_at": data["collected_at"],
            "coverage": "administrator_pod_export", "stream_complete": all(checks),
            "scope": scope, "post_count": posts, "comment_count": comments, "records": records,
            "exercise_id": scope.get("exercise_id"), "membership": None,
            "membership_snapshots": data.get("membership_snapshots", []),
            "warnings": [] if all(checks) else ["Eksporto pilnumas nepatvirtintas; turinys išsaugotas kaip nepilna imtis."]}
