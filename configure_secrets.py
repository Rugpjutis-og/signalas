"""Local terminal entry; entered secrets are hidden and never printed."""
import argparse
import getpass
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from integration_config import set_secret


def web_entry(port=0, path=None):
    """One-use loopback form. No credentials in logs, URLs, or page responses."""
    path = path or "/" + secrets.token_urlsafe(24)
    csrf = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            content = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def valid_path(self):
            return self.path == path and self.headers.get("Host") == "127.0.0.1:%s" % self.server.server_port

        def do_GET(self):
            if not self.valid_path():
                self.reply(404, "Nerasta")
                return
            self.reply(200, ("""<!doctype html><html lang="lt"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signalas · Diasporos prijungimas</title>
<style>body{font:16px system-ui;background:#f5f7fb;color:#23324c;margin:0;padding:30px}
main{max-width:480px;margin:8vh auto;background:white;border:1px solid #e1e6ef;border-radius:16px;padding:28px}
h1{font-size:23px}p{line-height:1.6;color:#65728a}label{display:block;margin-top:20px}
input{box-sizing:border-box;width:100%;padding:12px;margin:8px 0 20px;border:1px solid #bcc6db;border-radius:8px;font:inherit}
button{padding:12px 18px;border:0;border-radius:8px;background:#5369df;color:white;font:inherit;cursor:pointer}
input:focus,button:focus-visible{outline:3px solid #a5b1ff;outline-offset:3px}</style>
<main><h1>Diasporos prijungimas</h1><p>Paskyra: <strong>pax089</strong></p>
<p>Įrašykite slaptažodį. Jis bus išsaugotas tik vietiniame „Signalo“ .env faile.
Ši vienkartinė forma po išsaugojimo užsidarys.</p>
<form method="post" autocomplete="off"><input name="csrf" type="hidden" value="__CSRF__"><label for="password">Diasporos slaptažodis</label>
<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Išsaugoti prisijungimą</button></form></main></html>""").replace("__CSRF__", csrf))

        def do_POST(self):
            # Embedded browsers can omit/rewrite Origin. A secret form token plus
            # the loopback Host/path bind the submission to this one-use page.
            if not self.valid_path():
                self.reply(403, "Užklausa atmesta")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384:
                    raise ValueError()
                values = parse_qs(self.rfile.read(size).decode("utf-8"), keep_blank_values=True)
                if not secrets.compare_digest(values.get("csrf", [""])[0], csrf):
                    self.reply(403, "Atnaujinkite puslapį ir bandykite dar kartą.")
                    return
                set_secret("DIASPORA_PASSWORD", values.get("password", [""])[0])
            except (ValueError, OSError, UnicodeError):
                self.reply(400, "Nepavyko išsaugoti. Grįžkite ir įrašykite netuščią vienos eilutės slaptažodį.")
                return
            self.reply(200, '<!doctype html><meta charset="utf-8"><title>Išsaugota</title><p>Prisijungimas išsaugotas. Šį skirtuką galite uždaryti ir grįžti į pokalbį.</p>')
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    with HTTPServer(("127.0.0.1", port), Handler) as server:
        expiry = threading.Timer(900, server.shutdown)
        expiry.daemon = True
        expiry.start()
        print("http://127.0.0.1:%s%s" % (server.server_port, path), flush=True)
        server.serve_forever()
        expiry.cancel()


def main():
    parser = argparse.ArgumentParser(description="Vietinis paslėptas prieigos duomenų įvedimas")
    parser.add_argument("service", choices=("diaspora", "openai"), nargs="?", default="diaspora")
    parser.add_argument("--web", action="store_true", help="Vienkartinė vietinė Diasporos slaptažodžio forma")
    args = parser.parse_args()
    if args.web:
        if args.service != "diaspora":
            parser.error("--web skirtas Diasporos prisijungimui")
        web_entry()
        return
    name = "DIASPORA_PASSWORD" if args.service == "diaspora" else "OPENAI_API_KEY"
    value = getpass.getpass("Diasporos slaptažodis (rašant simbolių nesimatys): " if args.service == "diaspora"
                            else "OpenAI API raktas (rašant simbolių nesimatys): ")
    set_secret(name, value)
    print("Išsaugota vietiniame .env. Slapta reikšmė neišvedama.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError) as error:
        print("Nepavyko išsaugoti. Paleiskite įvedimą įprastame terminale ir įrašykite netuščią reikšmę.")
        raise SystemExit(1)
