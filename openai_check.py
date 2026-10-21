"""Explicit OpenAI credential check; no generation or exercise data is sent."""
import json
import os
from pathlib import Path
from integration_config import settings
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import monitoring


ROOT = Path(__file__).resolve().parent


def api_key(root=ROOT):
    key = settings(root).get("OPENAI_API_KEY", "").strip()
    if not key or any(char.isspace() for char in key):
        raise ValueError("Įrašykite raktą į projekto .env: OPENAI_API_KEY=... arba nustatykite aplinkos kintamąjį.")
    return key


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def check(root=ROOT):
    request = Request("https://api.openai.com/v1/models",
                      headers={"Authorization": "Bearer " + api_key(root),
                               "Accept": "application/json"})
    try:
        with build_opener(NoRedirect).open(request, timeout=20) as response:
            result = json.load(response)
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ValueError("Gautas neatpažintas API atsakymas.")
    except HTTPError as error:
        monitoring.http_failure(error, root)
        messages = {
            401: "API atmetė raktą. Patikrinkite jo galiojimą.",
            403: "Raktui neleidžiama skaityti modelių sąrašo. Patikrinkite projekto rakto teises.",
            429: "API užklausų arba paskyros limitas pasiektas. Patikrinkite OpenAI paskyrą.",
        }
        raise ValueError(messages.get(error.code, "OpenAI API ryšio klaida (HTTP %s)." % error.code)) from None
    except (URLError, TimeoutError, OSError):
        monitoring.record("openai", "api_connection", root)
        raise ValueError("Nepavyko pasiekti OpenAI API. Patikrinkite interneto ryšį.") from None
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Gautas neatpažintas API atsakymas.") from None
    # A models-list check cannot prove that paid generation has available credit.
    monitoring.access_recovered(root)
    return "OpenAI API ryšys veikia. Patikrinta prieiga prie modelių sąrašo; AI analizė nevykdyta."


if __name__ == "__main__":
    try:
        print(check())
    except ValueError as error:
        print(str(error))
        raise SystemExit(1)
