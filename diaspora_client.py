"""Paginated authenticated account stream and own profile; never whole-pod access."""
import json
import math
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, quote
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from content import source_url
from platform_overview import adapt_diaspora_post, adapt_diaspora_comment


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf = None
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "authenticity_token":
            self.csrf = attrs.get("value")
        if tag == "meta" and attrs.get("name") == "csrf-token":
            self.csrf = attrs.get("content")
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "meta" and attrs.get("property") == "og:url":
            self.canonical = attrs.get("content")


class SameOriginRedirect(HTTPRedirectHandler):
    def __init__(self, base):
        self.origin = urlsplit(base)[:2]

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if urlsplit(newurl)[:2] != self.origin:
            raise ValueError("Diaspora nukreipė į kitą domeną; prisijungimo duomenys neperduoti.")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class DiasporaClient:
    def __init__(self, base, username, password):
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("DIASPORA_BASE_URL turi būti HTTPS platformos adresas.")
        if not username or not password:
            raise ValueError("Trūksta DIASPORA_USERNAME arba DIASPORA_PASSWORD; naudokite configure_secrets.py diaspora.")
        self.base = base.rstrip("/")
        self.username, self.password = username, password
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()), SameOriginRedirect(self.base))

    def request(self, path, *, data=None, accept="application/json"):
        url = urljoin(self.base + "/", path)
        if urlsplit(url)[:2] != urlsplit(self.base)[:2]:
            raise ValueError("Duomenų gavimo adresas turi priklausyti tai pačiai Diasporai.")
        headers = {"Accept": accept, "User-Agent": "Signalas/1.0 (authorized read-only collection)"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = self.base
            headers["Referer"] = self.base + "/users/sign_in"
        try:
            with self.opener.open(Request(url, data=data, headers=headers), timeout=25) as response:
                # Bound memory. Never save session cookies, login HTML, or error bodies.
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError("Diasporos atsakymas viršijo bandymo dydžio ribą.")
                return body.decode("utf-8"), response.geturl(), response.headers.get("Content-Type", "")
        except HTTPError as error:
            raise ValueError("Diasporos užklausa nepavyko (HTTP %s). Patikrinkite prieigą." % error.code) from None
        except (URLError, OSError, UnicodeError):
            raise ValueError("Nepavyko saugiai perskaityti Diasporos atsakymo.") from None

    def login(self):
        html, _, _ = self.request("/users/sign_in", accept="text/html")
        metadata = PageMetadata()
        metadata.feed(html)
        if not metadata.csrf:
            raise ValueError("Diasporos prisijungimo forma neatpažinta.")
        data = urlencode({"authenticity_token": metadata.csrf, "user[username]": self.username,
                          "user[password]": self.password, "user[remember_me]": "0"}).encode()
        html, url, _ = self.request("/users/sign_in", data=data, accept="text/html")
        if urlsplit(url).path == "/users/sign_in" or 'name="user[otp_attempt]"' in html:
            raise ValueError("Prisijungimas nepatvirtintas. Patikrinkite slaptažodį arba dviejų veiksnių autentifikavimą.")
        return True

    def json(self, path):
        body, url, content_type = self.request(path)
        if "json" not in content_type or urlsplit(url).path == "/users/sign_in":
            raise ValueError("Vietoje Diasporos JSON gautas prisijungimo ar kitas puslapis.")
        try:
            return json.loads(body)
        except ValueError:
            raise ValueError("Netaisyklingas Diasporos JSON atsakymas.") from None

    def canonical(self, post_id):
        # This is a documented resource request, not an invented sourceUrl.
        # The original link is taken ONLY from the returned page's metadata.
        html, _, _ = self.request("/posts/" + quote(str(post_id), safe=""), accept="text/html")
        metadata = PageMetadata()
        metadata.feed(html)
        if not metadata.canonical:
            return None
        return source_url(urljoin(self.base + "/", metadata.canonical))

    def image(self, address):
        """Read a known same-pod raster image with the existing private session."""
        parsed = urlsplit(address)
        if parsed[:2] != urlsplit(self.base)[:2] or parsed.username or parsed.password:
            raise ValueError("Nuotraukos adresas turi priklausyti autorizuotai HTTPS platformai.")
        try:
            with self.opener.open(Request(address, headers={"Accept": "image/*", "User-Agent": "Signalas/1.0"}), timeout=25) as response:
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError("Nuotrauka viršija saugaus perdavimo dydį.")
        except (HTTPError, URLError, OSError):
            raise ValueError("Nepavyko gauti autorizuotai prieinamos nuotraukos.") from None
        # This pod labels actual WebP bytes text/plain + nosniff. Recognize a
        # raster signature; never forward an HTML login page or executable SVG.
        if body[:4] == b'RIFF' and body[8:12] == b'WEBP':
            return body, 'image/webp'
        if body.startswith(b'\x89PNG\r\n\x1a\n'):
            return body, 'image/png'
        if body.startswith(b'\xff\xd8\xff'):
            return body, 'image/jpeg'
        if body[:6] in (b'GIF87a', b'GIF89a'):
            return body, 'image/gif'
        raise ValueError("Šaltinis nepateikė atpažįstamos nuotraukos.")

    def stream(self, path):
        # This Diaspora release returns 15 rows per page. That is a server page
        # size, not a total collection limit. Overlap the boundary second because
        # Rails truncates max_time to integer seconds while posts have fractions.
        entries, seen, cursor, pages = [], set(), None, 0
        while True:
            page = self.json(path + ("?" + urlencode({"max_time": cursor}) if cursor is not None else ""))
            pages += 1
            if not isinstance(page, list):
                raise ValueError("Diasporos srauto formatas neatpažintas.")
            for entry in page:
                if not isinstance(entry, dict) or entry.get("id") is None or not entry.get("guid"):
                    raise ValueError("Srauto įrašui trūksta pastovaus ID; ankstesnė imtis nepakeista.")
                if entry["guid"] not in seen:
                    seen.add(entry["guid"])
                    entries.append(entry)
            if len(page) < 15:
                return entries, pages
            try:
                oldest = min(datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).timestamp() for e in page)
            except (KeyError, TypeError, ValueError):
                raise ValueError("Trūksta srauto puslapiavimui būtinos datos; ankstesnė imtis nepakeista.") from None
            next_cursor = math.floor(oldest) + 1
            if cursor is not None and next_cursor >= cursor:
                # A full page inside one second cannot be exhausted reliably
                # with this timestamp-only endpoint. Never silently skip rows.
                raise ValueError("Diasporos laiko žymos neleidžia tęsti puslapiavimo neprarandant įrašų. Ankstesnė imtis nepakeista; reikia administratoriaus eksporto.")
            cursor = next_cursor

    def collect(self):
        raw_posts, feed_pages = self.stream("/stream.json")
        profile = self.json("/u/" + quote(self.username, safe=""))
        if not isinstance(profile, dict) or profile.get("is_own_profile") is not True or not profile.get("guid"):
            raise ValueError("Nepavyko patvirtinti savo profilio; ankstesnė imtis nepakeista.")
        own_posts, profile_pages = self.stream("/people/" + quote(profile["guid"], safe="") + "/stream.json")
        source = urlsplit(self.base).hostname
        records, seen, warnings = [], set(), []
        for entry in raw_posts + own_posts:
            identity = entry.get("id") if isinstance(entry, dict) else None
            guid = entry.get("guid") if isinstance(entry, dict) else None
            if identity is None or not guid or guid in seen:
                continue
            seen.add(guid)
            raw = self.json("/posts/" + quote(str(identity), safe="") + ".json")
            if raw.get("guid") != guid:
                raise ValueError("Diasporos detalės neatitinka srauto įrašo.")
            try:
                original = self.canonical(identity)
            except ValueError:
                original = None
                warnings.append("Vieno įrašo originalo nuorodos nepavyko patvirtinti.")
            post = adapt_diaspora_post(raw, source=source, exercise_id=None, sourceUrl=original,
                                      interactions_complete=True, source_base_url=self.base)
            post["public"] = raw.get("public")
            records.append(post)
            interactions = raw.get("interactions") or {}
            comments = interactions.get("comments")
            if not isinstance(comments, list):
                comments = []
            earlier = []
            for raw_comment in sorted(comments, key=lambda c: c.get("created_at") or ""):
                comment = adapt_diaspora_comment(raw_comment, source=source, exercise_id=None,
                                                parentSourceUrl=original, source_base_url=self.base)
                if not comment.get("id"):
                    warnings.append("Praleistas komentaras be pastovaus šaltinio ID.")
                    continue
                comment["parent_id"] = post["id"]
                comment["parent_post"] = {key: post.get(key) for key in
                                           ("id", "published_at", "text", "media", "sourceUrl")}
                comment["conversation_context"] = list(earlier)
                earlier.append({key: comment.get(key) for key in
                                ("id", "published_at", "text", "media", "sourceUrl", "parentSourceUrl")})
                records.append(comment)
        return {"collected_at": datetime.now(timezone.utc).isoformat(), "source": source,
                "mode": "live_sample", "coverage": "account_stream_and_own_profile",
                "stream_complete": False, "exercise_id": None, "membership": None,
                "limits": {"post_limit": None, "pages_read": feed_pages + profile_pages, "comments_truncated": False},
                "account_scope": {"feed_posts": len(raw_posts), "own_profile_posts": len(own_posts),
                                  "feed_pages": feed_pages, "profile_pages": profile_pages,
                                  "pagination_complete": True},
                "post_count": len(seen), "comment_count": sum(p["kind"] == "comment" for p in records),
                "records": records, "warnings": warnings}
